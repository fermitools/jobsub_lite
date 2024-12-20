#!/bin/bash

echo "Environment:"
echo "============"
printenv | sort
echo "============"
echo "Files:"
echo "============"
ls -alR
echo "============"
echo "Products:"
echo "============"


# get osg 3.6 tools...
. /cvmfs/oasis.opensciencegrid.org/osg-software/osg-wn-client/3.6/current/el7-x86_64/setup.sh

which gfal-ls

for common_setup in /cvmfs/fermilab.opensciencegrid.org/products/common/etc/setups.sh
do
if [ -r $common_setup ]
then
    ls -l $common_setup
    . $common_setup
    break
fi
done
setup htgettoken
setup ifdhc
ups active

echo "============"
echo "Token:"
echo "============"
httokendecode
echo "============"
echo "Token: direct"
echo "============"
echo .condor_creds/*.use
cat  .condor_creds/*.use
httokendecode .condor_creds/*.use
echo "============"
echo "ifdh ls"
echo "============"
ifdh ls --force=https /pnfs/fermilab/users/$USER
echo "============"
for f in $*
do
   if [ -r $f ]
   then
       echo "Verified $f exists"
   else
       echo "File $f not found, failing job.."
       exit 1
   fi
done

# put something in any -d TAG /return/path areas for testing
outdirs=`printenv | grep '^CONDOR_DIR_' | sed -e 's/=.*//'`
echo "=== out dirs: $outdirs ==="
for od in $outdirs
do
   eval "echo $od = \$$od"
   eval "echo test $od > \$$od/testout.txt"
done

# now sleep for a bit
sleep 300
exit 0
