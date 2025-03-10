#!/bin/sh -x

{% if token is defined and token %}
{% if role and role != 'Analysis' %}
#export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}_{{role | lower}}.use
export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}_{{role | lower}}_{{oauth_handle}}.use
{% else %}
#export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}.use
export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}_{{oauth_handle}}.use
{% endif %}
{% endif %}

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
    {%if outurl%}
    {% set filebase %}sambegin.$CLUSTER.$PROCESS{% endset %}
    IFDH_CP_MAXRETRIES=1 ${JSB_TMP}/ifdh.sh cp ${JSB_TMP}/JOBSUB_ERR_FILE {{outurl}}/{{filebase}}.err
    IFDH_CP_MAXRETRIES=1 ${JSB_TMP}/ifdh.sh cp ${JSB_TMP}/JOBSUB_LOG_FILE {{outurl}}/{{filebase}}.out
    {%endif%}
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
    . /cvmfs/fermilab.opensciencegrid.org/packages/common/setup-env.sh
    sos=$(spack arch --operating-system)
    spack env activate ifdh_env_${sos}_${IFDH_VERSION:-current} ||
      echo Falling back to current ifdhc for this operation >&2 &&
      spack env activate ifdh_env_${sos}_current
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


################################################################################
## main ()                                                            ##########
################################################################################
#EXPERIMENT=$1
#DEFN=$2
#PRJ_NAME=$3
#GRID_USER=$4

export JSB_TMP=$_CONDOR_SCRATCH_DIR/jsb_tmp
mkdir -p $JSB_TMP
redirect_output_start
setup_ifdh_env
echo `date` BEGIN executing sambegin.sh
>&2 echo `date` BEGIN executing sambegin.sh
${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID BEGIN EXECUTION sambegin.sh"

if [ "${KRB5CCNAME}" != "" ]; then
   BK=`basename ${KRB5CCNAME}`
   if [ -e "${_CONDOR_JOB_IWD}/${BK}" ]; then
      export KRB5CCNAME="${_CONDOR_JOB_IWD}/${BK}"
      chmod 400 ${KRB5CCNAME}
      (while [ 0 ]; do kinit -R; sleep 3600 ; done ) &
   fi
fi


if [ "$SAM_STATION" = "" ]; then
SAM_STATION=$1
fi
if [ "$SAM_GROUP" = "" ]; then
SAM_GROUP=$1
fi
if [ "$SAM_DATASET" = "" ]; then
SAM_DATASET=$2
fi
if [ "$SAM_PROJECT" = "" ]; then
SAM_PROJECT=$3
fi
if [ "$SAM_USER" = "" ]; then
SAM_USER=$4
fi

extra_projects=""
suffix=""
first=true
for SAM_DATASET in $SAM_DATASET {{" ".join(dd_extra_dataset)}}
do

    SAM_PROJECT=$SAM_PROJECT$suffix

    ${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh describing definition"
    ${JSB_TMP}/ifdh.sh describeDefinition $SAM_DATASET


    yell() { echo "$0: $*" >&2; }
    die() { yell "$*"; exit 111; }
    try() { echo "$@"; "$@" || die "FAILED $*"; }

    num_tries=0
    max_tries=60
    if [ "$JOBSUB_MAX_SAM_STAGE_MINUTES" != "" ]; then
        max_tries=$JOBSUB_MAX_SAM_STAGE_MINUTES
    fi
    ${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh starting project $SAM_PROJECT"
    try ${JSB_TMP}/ifdh.sh startProject $SAM_PROJECT $SAM_STATION $SAM_DATASET $SAM_USER $SAM_GROUP
    while true; do
        STATION_STATE=${JSB_TMP}/$SAM_STATION.`date '+%s'`
        PROJECT_STATE=${JSB_TMP}/$SAM_DATASET.`date '+%s'`
        try ${JSB_TMP}/ifdh.sh dumpStation $SAM_STATION > $STATION_STATE
        grep $SAM_PROJECT $STATION_STATE > $PROJECT_STATE
        if [ "$?" != "0" ]; then
            num_tries=$(($num_tries + 1))
            if [ $num_tries -gt $max_tries ]; then
                echo "Something wrong with $SAM_PROJECT in $SAM_STATION, giving up"
                exit 111
            fi
            echo "attempt $num_tries of $max_tries: Sam Station $SAM_STATION still waiting for project $SAM_PROJECT, dataset $SAM_DATASET, sleeping 60 seconds"
            ${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh Waiting for $SAM_PROJECT $num_tries of $max_tries"
            sleep 60
            continue
        fi
        TOTAL_FILES=`cat $PROJECT_STATE | sed "s/^.* contains //" | sed "s/ total files:.*$//"`
        # scale for --dd-percentage
        TOTAL_FILES=$((TOTAL_FILES * {{dd_percentage}} / 100 ))
        CACHE_MIN=$TOTAL_FILES

        PROJECT_PREFETCH=`grep 'Per-project prefetched files' $STATION_STATE | sed "s/^.* files: //"`
        SCALED_PREFETCH=`echo "$PROJECT_PREFETCH/2" | bc`
        if [ $SCALED_PREFETCH -lt $CACHE_MIN ]; then
            CACHE_MIN=$SCALED_PREFETCH
        fi

        IN_CACHE=`cat $PROJECT_STATE | sed "s/^.*of these //" | sed "s/ in cache.*$//"`

        echo "$IN_CACHE files of $TOTAL_FILES are staged, waiting for $CACHE_MIN to stage"

        if [ $TOTAL_FILES -le 0 ]; then
            echo there are no files in $SAM_PROJECT! exiting....
            ${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh there are no files in $SAM_PROJECT! exiting...."
            cat $STATION_STATE
            exit 1
        fi
        if [ ! -s "$PROJECT_STATE" ]; then
            echo "$SAM_PROJECT" not found in  "$SAM_STATION" ! exiting....
            ${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh "$SAM_PROJECT" not found in  $SAM_STATION ! exiting...."
            cat $STATION_STATE
            exit 1
        fi
        if [ $IN_CACHE -ge $CACHE_MIN  ]; then
            echo $IN_CACHE files of $TOTAL_FILES are staged, success!
            break
        fi
        sleep 60

    done

    # keep track of "extra" projects made just to check staging...
    if $first
    then
       :
    else
       extra_projects="$extra_projects $SAM_PROJECT"
    fi
    suffix="_x"
    first=false

done

# if we started extra projects to check amount staged, end them
for PRJ_NAME in $extra_projects
do
    ${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh ending $PRJ_NAME"
    CPURL=`${JSB_TMP}/ifdh.sh findProject $PRJ_NAME ''`
    try ${JSB_TMP}/ifdh.sh  endProject $CPURL && echo success!
done

${JSB_TMP}/ifdh.sh log "$USER:$JOBSUBJOBID sambegin.sh exiting 0"

exit 0
