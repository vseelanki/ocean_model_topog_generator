#!/usr/bin/env python

def error(msg,code=9):
  print( 'Error: ' + msg)
  exit(code)


# Imports
try: import argparse
except: error('This version of python is not new enough. python 2.7 or newer is required.')
try: from netCDF4 import Dataset
except: error('Unable to import netCDF4 module. Check your PYTHONPATH.\n'
          +'Perhaps try:\n   module load python_netcdf4')
try: import numpy as np
except: error('Unable to import numpy module. Check your PYTHONPATH.\n'
          +'Perhaps try:\n   module load python_numpy')
import shutil as sh


def main():

  # Command line arguments
  parser = argparse.ArgumentParser(description=
       'Applies an "ice 9" algorithm to remove detached water from the topography. Also sets land elevation to 0.',
       epilog='Written by A.Adcroft, 2013.')
  parser.add_argument('filename', type=str,
                      help='netcdf file to read.')
  parser.add_argument('--variable', type=str,
                      nargs='?', default='depth',
                      help='Name of variable to plot.')
  parser.add_argument('--output', type=str,
                      nargs='?', default=' ',
                      help='name of the output file. If not specified, "iced_" is prepended to the name of the input file.')
  parser.add_argument('--shallow', type=float,
                      help='The "shallow" value (+ve, default 1.) to use when calculating the modified_mask. Wet points shallower than this are indicated with mask value of 2.')
  parser.add_argument('--iseed', type=int,
                      help='The seed for i-index, (iseed,jseed) should identify a non-land point in the input model topography.')
  parser.add_argument('--jseed', type=int,
                      help='The seed for j-index, (iseed,jseed) should identify a non-land point in the input model topography.')
  parser.add_argument('--analyze', action='store_true',
                      help='Report on impact of round shallow values to zero')

  optCmdLineArgs = parser.parse_args()

  nFileName = optCmdLineArgs.output
  if nFileName == ' ': nFileName = 'iced_'+optCmdLineArgs.filename
  shallow = 1
  if not optCmdLineArgs.shallow==None: shallow = optCmdLineArgs.shallow
  iseed,jseed = 150,130 #default seeds for Ocean point
  if not optCmdLineArgs.iseed==None: iseed = optCmdLineArgs.iseed
  if not optCmdLineArgs.jseed==None: jseed = optCmdLineArgs.jseed
	
  applyIce9(optCmdLineArgs.filename, nFileName, optCmdLineArgs.variable,
            iseed,jseed, shallow, optCmdLineArgs.analyze)

def applyIce9(fileName, nFileName, variable, i0, j0, shallow, analyze):

  iRg = Dataset( fileName, 'r' );
  iDepth = iRg.variables[variable] # handle to the variable
  depth = -iDepth[:] # Read the data
  print( 'Range of input depths: min=',np.amin(depth),'max=',np.amax(depth))

  # Open new netcdf file
  if fileName==nFileName: error('Output file must be different from the input file')
  try: rg=Dataset( nFileName, 'w', format='NETCDF3_CLASSIC' );
  except: error('There was a problem opening "'+nFileName+'".')

  (ny, nx) = depth.shape
  rg.createDimension('nx',nx)
  rg.createDimension('ny',ny)
  rgDepth = rg.createVariable('depth','f4',('ny','nx'))
  rgDepth.units = iDepth.units
#  rgDepth.standard_name = iDepth.standard_name
  rgDepth.description = 'Non-negative nominal thickness of the ocean at cell centers'
  rg.createDimension('ntiles',1)

  # A mask based solely on value of depth
  #notLand = np.where( depth<0, 1, 0)
  #notLand = ice9it(600,270,depth)
  #notLand = ice9it(1200,540,depth) #0.125 deg
  #notLand = ice9it(150,130,depth) #1deg and 0.5deg
  while depth[j0,i0] >= 0: 
     print("Seed is not wet! Increasing jseed by 10")
     j0 += 10
  if depth[j0,i0] >= 0:
     error("There is a problem with seed that could not be resolved. The seed location is not in the ocean!")  
	
  notLand = ice9it(i0,j0,depth)

  rgWet = rg.createVariable('wet','f4',('ny','nx'))
  rgWet.long_name = 'Wet/dry mask'
  rgWet.description = 'Values: 1=Ocean, 0=Land'
  rgWet[:] = notLand # + (1-notLand)*0.3*np.where( depth<0, 1, 0)

  rgDepth[:] = np.where(depth<0, -depth*notLand, 0) # Change sign here. Until this point depth has actually been elevation.

  if 'h2' in iRg.variables: # Need to copy over list of edits
    rgH2 = rg.createVariable('h2','f4',('ny','nx'))
    rgH2.units = iDepth.units+'^2'
    rgH2.standard_name = 'Variance of sub-grid scale topography'
    rgH2[:] = iRg.variables['h2'][:]

  if 'h_std' in iRg.variables: # Need to copy over list of edits
    rgHstd = rg.createVariable('h_std','f4',('ny','nx'))
    rgHstd.units = iDepth.units
    rgHstd.standard_name = 'Standard deviation of sub-grid scale topography in grid cell'
    rgHstd[:] = iRg.variables['h_std'][:]

  if 'h_min' in iRg.variables: # Need to copy over list of edits
    rgHmin = rg.createVariable('h_min','f4',('ny','nx'))
    rgHmin.units = iDepth.units
    rgHmin.standard_name = 'Minimum topography height data in grid cell'
    rgHmin[:] = iRg.variables['h_min'][:]

  if 'h_max' in iRg.variables: # Need to copy over list of edits
    rgHmax = rg.createVariable('h_max','f4',('ny','nx'))
    rgHmax.units = iDepth.units
    rgHmax.standard_name = 'Maximum topography height data in grid cell'
    rgHmax[:] = iRg.variables['h_max'][:]

  if 'zEdit' in iRg.variables: # Need to copy over list of edits
    rgMod = rg.createVariable('modified_mask','f4',('ny','nx'))
    rgMod.long_name = 'Modified mask'
    rgMod.description = 'Values: 1=Ocean, 0=Land, -1 indicates water points removed by "Ice 9" algorithm. 2 indicates wet points that are shallower than 1m deep.'
    rgMod[:] = notLand - (1-notLand)*np.where( depth<0, 1, 0) + np.where( (notLand>0) & (depth>-shallow), 1, 0)
    n = len(iRg.variables['zEdit'])
    nEd = rg.createDimension('nEdits',n)
    iEd = rg.createVariable('iEdit','i4',('nEdits',))
    iEd.long_name = 'i-index of edited data'
    jEd = rg.createVariable('jEdit','i4',('nEdits',))
    jEd.long_name = 'j-index of edited data'
    zEd = rg.createVariable('zEdit','f4',('nEdits',))
    zEd.long_name = 'Original value of height data'
    zEd.units = iDepth.units
    iEd[:] = iRg.variables['iEdit'][:]
    jEd[:] = iRg.variables['jEdit'][:]
    zEd[:] = iRg.variables['zEdit'][:]

  rg.close()
  print( 'File "%s" written.'%(nFileName))

  # Analyze the shallow points
  if analyze:
    print( 'Analyzing...')
    numNotLand = np.count_nonzero(notLand)
    print( '# of wet points after Ice 9 = %i'%(numNotLand))
    newDepth = depth*np.where(depth*notLand <= -shallow, 1, 0)
    numNewWet = np.count_nonzero(newDepth)
    print( '# of wet points deeper than %f = %i'%(-shallow,numNewWet))
    print( '%i - %i = %i fewer points left'%(numNotLand,numNewWet,numNotLand-numNewWet))
    newWet = ice9it(i0,j0,newDepth)
    numNewDeep = np.count_nonzero(newWet)
    print( '# of wet deep points after Ice 9 = %i'%(numNewDeep))
    print( '%i - %i = %i fewer points left'%(numNewWet,numNewDeep,numNewWet-numNewDeep))
  

def ice9it(i,j,depth):
  # Iterative implementation of "ice 9"
  wetMask = 0*depth
  (nj,ni) = wetMask.shape
  stack = set()
  stack.add( (j,i) )
  while stack:
    (j,i) = stack.pop()
    if wetMask[j,i] or depth[j,i] >= 0: continue
    wetMask[j,i] = 1
    if i>0: stack.add( (j,i-1) )
    else: stack.add( (j,ni-1) )
    if i<ni-1: stack.add( (j,i+1) )
    else: stack.add( (0,j) )
    if j>0: stack.add( (j-1,i) )
    if j<nj-1: stack.add( (j+1,i) )
    else: stack.add( (j,ni-1-i) )
  return wetMask

# Invoke main()
if __name__ == '__main__': main()

