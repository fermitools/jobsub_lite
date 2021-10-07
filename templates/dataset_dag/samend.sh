#!/bin/sh -x

export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}.use
export BEARER_TOKEN=`cat "$BEARER_TOKEN_FILE"`

setup_ifdh_env(){
#
# create ifdh.sh which runs
# ifdh in a seperate environment to
# keep it from interfering with users ifdh set up
#
cat << '_HEREDOC_' > ${JSB_TMP}/ifdh.sh
#!/bin/sh
#
touch .empty_file
which ifdh > /dev/null 2>&1
has_ifdh=$?
if [ "$has_ifdh" -ne "0" ] ; then
    unset PRODUCTS
    for setup_file in /cvmfs/fermilab.opensciencegrid.org/products/common/etc/setups /grid/fermiapp/products/common/etc/setups.sh /fnal/ups/etc/setups.sh ; do
      if [ -e "$setup_file" ] && [ "$has_ifdh" -ne "0" ]; then
         source $setup_file
         ups exist ifdhc $IFDH_VERSION
         has_ifdh=$?
         if [ "$has_ifdh" = "0" ] ; then
             setup ifdhc $IFDH_VERSION
             break
         else
            unset PRODUCTS
         fi
     fi
   done
fi
which ifdh > /dev/null 2>&1
if [ "$?" -ne "0" ] ; then
    echo "Can not find ifdh version $IFDH_VERSION ,exiting!"
    echo "Can not find ifdh version $IFDH_VERSION ,exiting! ">&2
    exit 1
else
    ifdh "$@"
    exit $?
fi
_HEREDOC_
chmod +x ${JSB_TMP}/ifdh.sh
}
            

echo `date` BEGIN executing /fife/local/scratch/uploads/fermilab/mengel/2020-01-14_162931.318256_6730/fife_wrap_20200114_162957_3316054.samend.sh
>&2 echo `date` BEGIN executing /fife/local/scratch/uploads/fermilab/mengel/2020-01-14_162931.318256_6730/fife_wrap_20200114_162957_3316054.samend.sh
export JSB_TMP=$_CONDOR_SCRATCH_DIR/jsb_tmp
mkdir -p $JSB_TMP
setup_ifdh_env
PRJ_NAME=$1


if [ "${KRB5CCNAME}" != "" ]; then
   BK=`basename ${KRB5CCNAME}`
   if [ -e "${_CONDOR_JOB_IWD}/${BK}" ]; then
      export KRB5CCNAME="${_CONDOR_JOB_IWD}/${BK}"
      chmod 400 ${KRB5CCNAME}
      (while [ 0 ]; do kinit -R; sleep 3600 ; done ) &
   fi
fi
            
export IFDH_BASE_URI=http://samweb.fnal.gov:8480/sam/samdev/api
CPURL=`${JSB_TMP}/ifdh.sh findProject $PRJ_NAME ''` 
${JSB_TMP}/ifdh.sh  endProject $CPURL
EXITSTATUS=$?
echo `date` ifdh endProject $CPURL exited with status $EXITSTATUS
>&2 echo `date` ifdh endProject $CPURL exited with status $EXITSTATUS
exit $EXITSTATUS
