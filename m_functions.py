# -*- coding: utf-8 -*-

'''
-------------------

*By: Michelangelo Traina (LPNHE, Sorbonne Universite) to study skipper CCD data
Module with various functions used in the CCD testing package

-------------------
'''

##############################################################################
# import json and read configuration file
import json
import numpy as np

#def infomod(): #to get functions.py function caller module)
#    import inspect
#    f = inspect.stack()[-1][1]
#    return f

with open('config.json') as config_file:
    config = json.load(config_file)
test = config['test']
reverse = config['reverse']
registersize = config['ccd_active_register_size']
prescan = config['prescan']
overscan = config['overscan']
analysisregion = config['analysis_region']


#####################################################################
#prescan+activeregion+prescan(physical)+overscan(unphysical)#########
def selectImageRegion(image,analysisregion):
    import warnings
    if analysisregion == 'full' or test == 'linearity': return image
    elif analysisregion == 'overscan':
        rowidx = np.arange(np.size(image,0))
        if np.size(image,1) > prescan+registersize+prescan:
            colidx = np.arange(prescan+registersize+prescan,np.size(image,1))
            image_overscan = image[np.ix_(rowidx, colidx)]
        else:
            colidx = np.arange(np.size(image,1))
            image_overscan = image[np.ix_(rowidx, colidx)]
            print('Image has no overscan. Falling back to exposed pixels')
        return image_overscan
    elif analysisregion == 'exposed_pixels':
        rowidx = np.arange(np.size(image,0))
        lastexposedcolumn = min(np.size(image,1),prescan+registersize)
        colidx = np.arange(prescan,lastexposedcolumn)
        image_exposed = image[np.ix_(rowidx, colidx)]
        return image_exposed
    elif analysisregion == 'no_borders':
        rowidx = np.arange(1,np.size(image,0)-1)
        colidx = np.arange(1,np.size(image,1)-1)
        image_no_borders = image[np.ix_(rowidx, colidx)]
        return image_no_borders
    elif analysisregion == 'EPER':
        if np.size(image,1) > prescan+registersize:
            rowidx = np.arange(np.size(image,0))
            colidx = np.arange(prescan+registersize-10,prescan+registersize+10)
            image_eper = image[np.ix_(rowidx, colidx)]
            return image_eper
        else:
            warnings.warn('WARNING: Image has no overscan. EPER CTE estimation cannot be carried out.')
    else:
        print('WARNING: Analysis region defined incorrectly. Falling back to full image')
        return image

##############################################################################

from mpl_toolkits.axes_grid1 import make_axes_locatable
def make_colorbar_with_padding(ax):
    """
    Create colorbar axis that fits the size of a plot - detailed here: http://chris35wills.github.io/matplotlib_axis/
    """
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    return(cax)

def plot_spectrum(im_fft):
    from matplotlib.colors import LogNorm
    # A logarithmic colormap
    plt.imshow(np.abs(im_fft), norm=LogNorm(vmin=5))
    plt.colorbar()

def reject_outliers(data, m=2):                                                                            
#   return data[abs(data - median(data)) / mad(data, constant=1)< m]
    return data[abs(data - np.median(data)) < m * np.std(data)]   

def reject_outliers1(data, m = 2.):
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    return data[s<m]

def linefunction(x, q, m):
    return q+m*x

def gauss(x, *p):
    import numpy as np
    A, mu, sigma = p
    return A*np.exp(-(x-mu)**2/(2*sigma**2))
    
def factorial(n):
    facto=1
    for f in range(2,n+1): facto*=f
    return facto
        
def convolutionGaussianPoisson(q, *p):
    dcratep, npeaksp, amplip, sigmap = p
    f = 0
    npeaksp = 3
    for peaks in range(npeaksp):
        f +=  ( (dcratep**peaks * np.exp(-dcratep) / factorial(peaks)) * (amplip / np.sqrt(2 * np.pi * sigmap**2)) * np.exp( - (q - peaks)**2 / (2 * sigmap**2)) )
    return f
    
from math import log10, floor
def round_sig_2(x, sig=2):
    if x == 0: x = 0.00001
    return round(x, sig-int(floor(log10(abs(x))))-1)

def sigmaFinder(image, debug):
    import numpy as np
    from scipy.optimize import curve_fit
    import matplotlib.pyplot as plt
    if type(image) is np.ndarray:
        image = selectImageRegion(image,analysisregion)
        pcd = image.ravel()
        pcd = [s for s in pcd if s != 0]
        bins = int(max(pcd) - min(pcd))
    else:
        pcd = image; bins = 100
        if test != 'linearity': print("WARNING: Image provided in form of list (1D array). You're good if this is linearity test, else, check your code")
    try: pcdhistogram, binedges = np.histogram(pcd, bins, density=False)
    except: pcdhistogram, binedges = np.histogram(pcd, 100, density=False)
    if analysisregion == 'overscan': mostlikelyentry = np.array(pcd).mean(); mostlikelyentrycounts = pcdhistogram[np.argmax(pcdhistogram)]; sigma=np.array(pcd).std(); fwhm,fwhmcounts = float('nan'),float('nan')
    else:
        if reverse: #works well
            while (bins - np.argmax(pcdhistogram) < 30): #and reverse) or (np.argmax(pcdhistogram) < 30 and (not reverse)):
                bins += 10
                pcdhistogram, binedges = np.histogram(pcd, bins, density=False)
        #else: # did not understand wth is going on with four lines below
        #    while (np.argmax(pcdhistogram) < 30):
        #        bins += 10
        #        print(np.argmax(pcdhistogram))
        #        pcdhistogram, binedges = np.histogram(pcd, bins, density=False)
        mostlikelyentry = 0.5*(binedges[np.argmax(pcdhistogram)]+binedges[np.argmax(pcdhistogram)+1]) #pedestal estimation
        #find sigma using FWHM
        mostlikelyentrycounts = pcdhistogram[np.argmax(pcdhistogram)]
        try:
            #loop towards right tail of gaussian to find bin of FWHM. Loop condition 10-fold checks that we're not <= HM for a fluctuation
            bincounter = 1
            condition = np.ones(10)
            while(any(condition)):
                bincounter=bincounter+1
                for i in range (0,len(condition)): condition[i] = pcdhistogram[np.argmax(pcdhistogram)+bincounter+(i+1)] >  0.5*mostlikelyentrycounts
            #FWHM ADUs value
            fwhm = 0.5*( binedges[np.argmax(pcdhistogram)+bincounter] + binedges[np.argmax(pcdhistogram)+bincounter+1] )
            #find sigma using FWHM
            fwhmcounts = pcdhistogram[np.argmax(pcdhistogram) + bincounter]
            #sigma is: sigma  = 0.5*FWHM/sqrt(2ln2)
            sigma = abs(mostlikelyentry - fwhm)
            sigma = sigma/np.sqrt(2*np.log(2))
        except:
            fwhm, fwhmcounts = float('nan'),float('nan')
            mostlikelyentry=np.array(pcd).mean()
            sigma=np.array(pcd).std()
            print('Accurate noise estimation failed. Using pcd array statistics as fit guess: mean ='+str(round(mostlikelyentry,2))+' ADU and std= '+str(round(sigma,4))+' ADU')
    #now find accurate mean and stdev by fitting in proper range
    fitrange = 2.
    pcdinrange = [s for s in pcd if s > mostlikelyentry - fitrange*sigma and s < mostlikelyentry + fitrange*sigma] #remove pixels out of desired range
    pguess = [mostlikelyentrycounts,mostlikelyentry,sigma]
    try: binsinrange = int(bins/int(max(pcd) - min(pcd)))*int(max(pcdinrange) - min(pcdinrange)); pcdinrangehist, binedges = np.histogram(pcdinrange, binsinrange, density=False)
    except: binsinrange = 100+int(bins/100)*int(max(pcdinrange) - min(pcdinrange)); pcdinrangehist, binedges = np.histogram(pcdinrange, binsinrange, density=False)
    bincenters=(binedges[:-1] + binedges[1:])/2
    try:
        pfit, varmatrix = curve_fit(gauss, bincenters, pcdinrangehist, p0=pguess)
        pcdhistfit = gauss(bincenters,*pfit)
        amp,mu,std = pfit[0],pfit[1],abs(pfit[2])
        #print(mu,np.sqrt(np.diag(varmatrix))[1])
        if abs(np.sqrt(np.diag(varmatrix))[1]/mu) > 0.5: mu = mostlikelyentry #should be fine
        munc = np.sqrt(np.diag(varmatrix))[1]
        stdunc = np.sqrt(np.diag(varmatrix))[-1]
    except: amp, mu, std = pguess; pcdhistfit = gauss(bincenters,*pguess); munc,stdunc=0,0; print('Gaussian fit for noise evaluation failed. Fit guess values used')
    
    if debug:
        #bincenters=0.5*(binedges[1:] + binedges[:-1])
        #plt.plot(bincenters, pcdhistogram)
        #plt.show()
        #plt.clf()
        print('Most likely entry is:', mostlikelyentry)
        print('Most likely entry counts are:', mostlikelyentrycounts)
        print('FWHM is at:', fwhm)
        print('FWHM difference counts are:',fwhmcounts)
        print('Value of approximate gaussian std (noise) is:', round(sigma,4))
        print('Value of gaussian std (noise) is:', round(std,4))
        plt.plot(bincenters,pcdinrangehist,label='pcd')
        plt.plot(bincenters, pcdhistfit, label='fit curve')
        plt.title('$\mu=$' + str(round(mu,1)) + ' ADU, $\sigma=$' + str(round(std,3)) + ' ADU')
        plt.show()
        
    return amp, mu, std, munc, stdunc

from math import ceil,log

def pixelFFT(skipimage, rows, columns, Nskips, samplet):
    import numpy as np
    import matplotlib.pyplot as plt
    #from matplotlib.ticker import (NullFormatter, AutoMinorLocator, MultipleLocator)
    from scipy.fftpack import fft
    
    fftdata = np.zeros(Nskips, dtype=np.float64)
    
    for row in range(rows):
        for clmn in range(0,columns*Nskips,Nskips):
            fftskips = fft(skipimage[row,clmn:clmn+Nskips]-skipimage[row,clmn:clmn+Nskips].mean())
            fftdata += np.abs(fftskips)
    
    xfreq = 1/samplet
    xfreq = np.arange(0,xfreq,xfreq/Nskips)
    fftdata /= (rows*columns)
    
    #plt.plot(xfreq[1:int(Nskips/2)], np.abs(fftdata[1:int(Nskips/2)]), color='teal', label='Pixel Fast Fourier Transform across skips')
    #plt.legend(loc='upper right',prop={'size': 20})
    #plt.yscale('log')
    #plt.grid(color='grey', linestyle='-', linewidth=1)
    #plt.ylabel('FFT magnitude')
    #plt.xlabel('Frequency (Hz)')
    #plt.title('Full Image Fast Fourier Transform')
    fig,axs = plt.subplots(1,1)
    axs.plot(xfreq[1:int(Nskips/2)],np.abs(fftdata[1:int(Nskips/2)]), color='teal', label='Pixel Fast Fourier Transform across skips')
    axs.set_yscale('log')
    #axs.yaxis.set_major_locator(MultipleLocator( 10**(ceil( log( max(np.abs(fftdata))-min(np.abs(fftdata)), 10 ) ) -1 ) ))
    #axs.yaxis.set_minor_formatter(NullFormatter())
    axs.tick_params(axis='both', which='both', length=10, direction='in')
    axs.grid(color='grey', linestyle=':', linewidth=1, which='both')
    plt.setp(axs.get_yticklabels(), visible=True)
    axs.set_xlabel('Frequency (Hz)')
    axs.set_ylabel('FFT magnitude')
    axs.set_title('Full Image Fast Fourier Transform')
    
    return 0

def rowFFT(avgimage, rows, columns, samplet):
    import numpy as np
    import matplotlib.pyplot as plt
    #from matplotlib.ticker import (NullFormatter, AutoMinorLocator, MultipleLocator)
    from scipy.fftpack import fft
    
    fftdata = np.zeros(columns, dtype=np.float64)
    
    for row in range(rows):
        fftrow = fft(avgimage[row,0:columns]-avgimage[row,0:columns].mean())
        fftdata += np.abs(fftrow)
    
    xfreq = 1/samplet
    xfreq = np.arange(0,xfreq,xfreq/columns)
    fftdata /= (rows)
    
    #plt.plot(xfreq[1:int(columns/2)], np.abs(fftdata[1:int(columns/2)]), color='teal', label='Row Fast Fourier Transform')
    #plt.legend(loc='upper right',prop={'size': 20})
    #plt.yscale('log')
    #plt.ylabel('FFT magnitude')
    #plt.xlabel('Frequency (Hz)')
    #plt.title('Average Image Fast Fourier Transform')
    fig,axs = plt.subplots(1,1)
    axs.plot(xfreq[1:int(columns/2)], np.abs(fftdata[1:int(columns/2)]), color='teal', label='Row Fast Fourier Transform')
    axs.set_yscale('log')
    #axs.yaxis.set_major_locator(MultipleLocator( 10**(ceil(log(max(np.abs(fftdata))-min(np.abs(fftdata)),10))-1) ))
    axs.tick_params(axis='both', which='both', length=10, direction='in')
    axs.grid(color='grey', linestyle=':', linewidth=1, which='both')
    plt.setp(axs.get_yticklabels(), visible=True)
    axs.set_xlabel('Frequency (Hz)')
    axs.set_ylabel('FFT magnitude')
    axs.set_title('Average Image Fast Fourier Transform')

    return 0
