#!/bin/sh -x



#export BEARER_TOKEN_FILE=$PWD/.condor_creds/fermilab.use
export BEARER_TOKEN_FILE=$PWD/.condor_creds/fermilab_b355f5a23c.use



redirect_output_start(){
    exec 7>&1
    exec >${JSB_TMP}/JOBSUB_LOG_FILE
    exec 8>&2
    exec 2>${JSB_TMP}/JOBSUB_ERR_FILE
}

redirect_output_finish(){
    exec 1>&7 7>&-
    exec 2>&8 8>&-
    cat ${JSB_TMP}/JOBSUB_ERR_FILE 1>&2
    cat ${JSB_TMP}/JOBSUB_LOG_FILE


    IFDH_CP_MAXRETRIES=1 ${JSB_TMP}/ifdh.sh cp ${JSB_TMP}/JOBSUB_ERR_FILE https://fndcadoor.fnal.gov:2880/fermigrid/jobsub/jobs/2023_12_18/71a1aea7-4417-446c-920c-d3042a8f2b4b/samend.$CLUSTER.$PROCESS.err
    IFDH_CP_MAXRETRIES=1 ${JSB_TMP}/ifdh.sh cp ${JSB_TMP}/JOBSUB_LOG_FILE https://fndcadoor.fnal.gov:2880/fermigrid/jobsub/jobs/2023_12_18/71a1aea7-4417-446c-920c-d3042a8f2b4b/samend.$CLUSTER.$PROCESS.out

}

normal_exit(){
    redirect_output_finish
}

signal_exit(){
    echo "$@ "
    echo "$@ " 1>&2
    exit 255
}

trap normal_exit EXIT
trap "signal_exit received signal TERM"  TERM
trap "signal_exit received signal KILL" KILL
trap "signal_exit received signal ABRT" ABRT
trap "signal_exit received signal QUIT" QUIT
trap "signal_exit received signal ALRM" ALRM
trap "signal_exit received signal INT" INT
trap "signal_exit received signal BUS" BUS
trap "signal_exit received signal PIPE" PIPE

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


export JSB_TMP=$_CONDOR_SCRATCH_DIR/jsb_tmp
mkdir -p $JSB_TMP
redirect_output_start
setup_ifdh_env
echo `date` BEGIN executing samend.sh
>&2 echo `date` BEGIN executing samend.sh

if [ "$SAM_PROJECT" = "" ]; then
SAM_PROJECT=$1
fi
PRJ_NAME=$SAM_PROJECT


if [ "${KRB5CCNAME}" != "" ]; then
   BK=`basename ${KRB5CCNAME}`
   if [ -e "${_CONDOR_JOB_IWD}/${BK}" ]; then
      export KRB5CCNAME="${_CONDOR_JOB_IWD}/${BK}"
      chmod 400 ${KRB5CCNAME}
      (while [ 0 ]; do kinit -R; sleep 3600 ; done ) &
   fi
fi

CPURL=`${JSB_TMP}/ifdh.sh findProject $PRJ_NAME ''`
${JSB_TMP}/ifdh.sh  endProject $CPURL
EXITSTATUS=$?
echo `date` ifdh endProject $CPURL exited with status $EXITSTATUS
>&2 echo `date` ifdh endProject $CPURL exited with status $EXITSTATUS
exit $EXITSTATUS
