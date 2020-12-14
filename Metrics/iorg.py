#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import random
from skimage.measure import label, regionprops
from .utils import findFiles, getField, cKDTreeMethod, createCircularMask

# TODO: Implement loop over each scene to ascertain sensitivity to random 
#       sampling of reference locations for inhibition NNCDF

class circle():
    def __init__(self,r,img):
        self.x = random.randint(0,img.shape[1]-1)
        self.y = random.randint(0,img.shape[0]-1)
        
        self.xp = self.x + img.shape[1]
        self.yp = self.y + img.shape[0]
        
        self.xm = self.x - img.shape[1]
        self.ym = self.y - img.shape[0]        
        
        self.r = r

def checkOverlap(new,placedCircles):
    ovl = \
    any(pow(c.x  - new.x,2) + pow(c.y  - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.xm - new.x,2) + pow(c.yp - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.x  - new.x,2) + pow(c.yp - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.xp - new.x,2) + pow(c.yp - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.xm - new.x,2) + pow(c.y  - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.xp - new.x,2) + pow(c.y  - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.xm - new.x,2) + pow(c.ym - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.x  - new.x,2) + pow(c.ym - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles) or \
    any(pow(c.xp - new.x,2) + pow(c.ym - new.y,2) <= pow(c.r + new.r,2) for c 
        in placedCircles)
    return ovl

class IOrg():
    '''
    Class for computing the organisation index iOrg (Weger et al. 1992) from a
    cloud mask, using an inhibition nearest neighbour distribution, as proposed 
    by Benner & Curry (1998) and detailed in Antonissen (2019).
    
    Parameters
    ----------
    mpar : Dict (optional, but necessary for using the compute method)
       Specifies the following parameters:
           loadPath : Path to load .h5 files that contain a pandas dataframe
                      with a cloud mask field as one of the columns.
           savePath : Path to a .h5 containing a pandas dataframe whose columns
                      contain metrics and whose indices are scenes. One of 
                      these columns can be filled by 'iOrg'.
           save     : Boolean to specify whether to store the variables in
                      savePath/Metrics.h5
           resFac   : Resolution factor (e.g. 0.5), to coarse-grain the field.
           plot     : Boolean to specify whether to make plot with details on
                      this metric for each scene.
           con      : Connectivitiy for segmentation (1 - 4 seg, 2 - 8 seg)
           areaMin  : Minimum cloud size considered in computing metric
           fMin     : First scene to load
           fMax     : Last scene to load. If None, is last scene in set.
           fields   : Naming convention for fields, used to set the internal
                      field to be used to compute each metric. Must be of the 
                      form:
                           {'cm'  : CloudMaskName, 
                            'im'  : imageName, 
                            'cth' : CloudTopHeightName,
                            'cwp' : CloudWaterPathName}
                     
    '''
    def __init__(self, mpar=None):
        # Metric-specific parameters
        self.field    = 'Cloud_Mask_1km'
        self.maxTries = 100         # How many placement attempts per object
        self.numCalcs = 1           # How many times to do the placement
        self.plot     = False
        self.con      = 1
        self.areaMin  = 4
        
        if mpar is not None:
            # General parameters
            self.loadPath = mpar['loadPath']
            self.savePath = mpar['savePath']
            self.save     = mpar['save']
            self.saveExt  = mpar['saveExt']
            self.resFac   = mpar['resFac']
            self.plot     = mpar['plot']
            self.con      = mpar['con']
            self.areaMin  = mpar['areaMin']
            self.fMin     = mpar['fMin']
            self.fMax     = mpar['fMax']
            self.field    = mpar['fields']['cm']

    def metric(self,field):
        '''
        Compute metric(s) for a single field

        Parameters
        ----------
        field : numpy array of shape (npx,npx) - npx is number of pixels
            Cloud mask field.

        Returns
        -------
        iOrg : float
            Organisation index from comparison to inhibition nearest neighbour
            distribution.

        '''
        cmlab,num  = label(field,return_num=True,connectivity=self.con)
        regions    = regionprops(cmlab)
        
        cr = []; 
        xC = []; yC = []
        for i in range(len(regions)):
            props  = regions[i]
            if props.area > self.areaMin:
                y0, x0 = props.centroid
                xC.append(x0); yC.append(y0)
                cr.append(props.equivalent_diameter/2) # FIXME too simple?
        
        posScene = np.vstack((np.asarray(xC),np.asarray(yC))).T
        cr       = np.asarray(cr)
        cr = np.flip(np.sort(cr))                        # Largest to smallest
        
        print('Number of regions: ',posScene.shape[0],'/',num)

        if posScene.shape[0] < 1:
            return float('nan')
        
        iOrgs = np.zeros(self.numCalcs)
        for c in range(self.numCalcs):
            # Attempt to randomly place all circles in scene without ovelapping
            i=0; placedCircles = []; placeCount = 0
            while i < len(cr) and placeCount < self.maxTries:
                new = circle(cr[i],field)
                placeable = True
                
                # If the circles overlap -> Place again
                if checkOverlap(new,placedCircles):
                    placeable = False; placeCount += 1
                
                if placeable:
                    placedCircles.append(new)
                    i+=1; placeCount = 0
            
            if placeCount == self.maxTries:
                # FIXME should ideally start over again automatically
                print('Unable to place circles in this image') 
            else:
                if self.plot:
                    fig1 = plt.figure(figsize=(5,5)); ax = plt.gca()
                    ax.set_xlim((0,field.shape[1]));ax.set_ylim((0,field.shape[0]))
                    for i in range(len(placedCircles)):
                        circ = plt.Circle((placedCircles[i].xm,placedCircles[i].yp)
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].x ,placedCircles[i].yp)
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].xp,placedCircles[i].yp)
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].xm,placedCircles[i].y )
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].x ,placedCircles[i].y )
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].xp,placedCircles[i].y )
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].xm,placedCircles[i].ym)
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].x ,placedCircles[i].ym)
                                          ,placedCircles[i].r); ax.add_artist(circ)
                        circ = plt.Circle((placedCircles[i].xp,placedCircles[i].ym)
                                          ,placedCircles[i].r); ax.add_artist(circ)
                    ax.grid(which='both')
                    plt.show()
        
                ## Compute the nearest neighbour distances ##
                
                # Gather positions in array
                posRand = np.zeros((len(placedCircles),2))
                for i in range(len(placedCircles)):
                    posRand[i,0] = placedCircles[i].x
                    posRand[i,1] = placedCircles[i].y
                
                nndRand   = cKDTreeMethod(posRand,field)
                nndScene  = cKDTreeMethod(posScene,field)
                
                nbins = len(nndRand)+1
                bmin = np.min([np.min(nndRand),np.min(nndScene)])
                bmax = np.max([np.max(nndRand),np.max(nndScene)])
                bins = np.linspace(bmin,bmax,nbins)
                
                nndcdfRan = np.cumsum(np.histogram(nndRand, bins)[0])/len(nndRand)
                nndcdfSce = np.cumsum(np.histogram(nndScene,bins)[0])/len(nndScene)
                        
                ## Compute Iorg ##
                iOrg = np.trapz(nndcdfSce,nndcdfRan)  
                iOrgs[c] = iOrg
                
                if self.plot:
                    fig,axs=plt.subplots(ncols=4,figsize=(20,5))
                    
                    axs[0].imshow(field,'gray')
                    axs[0].set_title('Cloud mask of scene')
                    
                    axs[1].scatter(posScene[:,0],field.shape[0] - posScene[:,1],
                                   color='k',s=5)
                    axs[1].set_title('Scene centroids')
                    axs[1].set_xlim((0,field.shape[1]))
                    axs[1].set_ylim((0,field.shape[0]))
                    asp = np.diff(axs[1].get_xlim())[0] / \
                          np.diff(axs[1].get_ylim())[0]
                    axs[1].set_aspect(asp)
                    
                    axs[2].scatter(posRand[:,0],posRand[:,1],color='k',s=5)
                    axs[2].set_title('Random field centroids')
                    asp = np.diff(axs[2].get_xlim())[0] / \
                          np.diff(axs[2].get_ylim())[0]
                    axs[2].set_aspect(asp)
                    
                    axs[3].plot(nndcdfRan,nndcdfSce,'-',color='k')
                    axs[3].plot(nndcdfRan,nndcdfRan,'--',color='k')
                    axs[3].set_title('Nearest neighbour distribution')
                    axs[3].set_xlabel('Random field nearest neighbour CDF')
                    axs[3].set_ylabel('Scene nearest neighbour CDF')
                    axs[3].annotate(r'$I_{org} = $'+str(round(iOrg,3)),(0.7,0.1),
                                    xycoords='axes fraction')
                    asp = np.diff(axs[3].get_xlim())[0] / \
                          np.diff(axs[3].get_ylim())[0]
                    axs[3].set_aspect(asp)
                    plt.show()
        print(iOrgs)
        iOrg = np.mean(iOrgs)        
        return iOrg
        
    def verify(self):
        '''
        Verification with simple examples:
            1. Regular lattice of squares (iOrg -> 0)
            2. Randomly scattered points (iOrg -> 0.5)
            3. One large, uniform circle with noise around it (iOrg -> 1)
        
        Returns
        -------
        veri : List of floats
            List containing metric(s) for verification case.

        '''        
        # 1. Regular lattice of squares
        t1 = np.zeros((512,512))
        t1[::16,::16] = 1; t1[1::16,::16] = 1; 
        t1[::16,1::16] = 1; t1[1::16,1::16] = 1;
        
        # 2. Randomly scattered points
        posScene = np.random.randint(0, high=512, size=(1000,2))
        t2 = np.zeros((512,512))
        t2[posScene[:,0],posScene[:,1]] = 1
        
        # 3. One large, uniform circle with noise around it
        t3 = np.zeros((512,512)) 
        maw = 128
        mask = createCircularMask(maw,maw).astype(int)
        t3[:maw,:maw] = mask; #t3[maw-20:2*maw-20,maw-50:2*maw-50] = mask;
        tadd = np.random.rand(maw,maw)
        ind = np.where(tadd>0.4);  tadd[ind]=1
        ind = np.where(tadd<=0.4); tadd[ind]=0
        t3[:maw,:maw]+=tadd; t3[t3>1] = 1
        
        tests = [t1,t2,t3]
        
        aMin = self.areaMin
        self.areaMin = 0
        veri = []
        for i in range(len(tests)):
            iOrg = self.metric(tests[i])
            veri.append(iOrg)
        
        self.areaMin = aMin
        return veri
        
    def compute(self):
        '''
        Main loop over scenes. Loads fields, computes metric, and stores it.

        '''
        files, dates = findFiles(self.loadPath)
        files = files[self.fMin:self.fMax]
        dates = dates[self.fMin:self.fMax]

        if self.save:
            saveSt    = self.saveExt
            dfMetrics = pd.read_hdf(self.savePath+'/Metrics'+saveSt+'.h5')
        
        ## Main loop over files
        for f in range(len(files)):
            cm = getField(files[f], self.field, self.resFac, binary=True)
            print('Scene: '+files[f]+', '+str(f+1)+'/'+str(len(files)))
            
            iOrg = self.metric(cm)
            print('iOrg: ',iOrg) 

            if self.save:
                dfMetrics['iOrg'].loc[dates[f]] = iOrg
        
        if self.save:
            dfMetrics.to_hdf(self.savePath+'/Metrics'+saveSt+'.h5', 'Metrics',
                             mode='w')

if  __name__ == '__main__':
    mpar = {
            'loadPath' : '/Users/martinjanssens/Documents/Wageningen/Patterns-in-satellite-images/testEnv/Data/Filtered',
            'savePath' : '/Users/martinjanssens/Documents/Wageningen/Patterns-in-satellite-images/testEnv/Data/Metrics',
            'save'     : True, 
            'resFac'   : 1,     # Resolution factor (e.g. 0.5)
            'plot'     : True,  # Plot with details on each metric computation
            'con'      : 1,     # Connectivity for segmentation (1:4 seg, 2:8 seg)
            'areaMin'  : 4,     # Minimum cloud size considered for object metrics
            'fMin'     : 0,     # First scene to load
            'fMax'     : None,  # Last scene to load. If None, is last scene in set
           }
    iOrgGen = IOrg(mpar)
    iOrgGen.verify()
    iOrgGen.compute()
        
