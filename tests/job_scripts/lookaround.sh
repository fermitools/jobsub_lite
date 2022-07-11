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

for common_setup in /cvmfs/fermilab.opensciencegrid.org/products/common/etc/setups.sh /grid/fermiapp/products/common/etc/setups.sh
do
if [ -r $common_setup ]
then
    ls -l $common_setup
    . $common_setup
    break
fi
done
setup htgettoken
setup ifdhc v2_6_0 -q python36, ifdhc_config v2_6_0 
export IFDH_TOKEN_ENABLE=1
export IFDH_PROXY_ENABLE=0
ups active

echo "============"
echo "Token:"
echo "============"
httokendecode
echo "============"
echo "Token: direct"
echo "============"
cat $_CONDOR_CREDS/*.use
decode_token.sh $_CONDOR_CREDS/*.use
echo "============"
echo "ifdh ls"
echo "============"
ifdh ls --force=https /pnfs/fermilab/users/mengel
