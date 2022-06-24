#!/bin/bash 
cd $_CONDOR_SCRATCH_DIR
###################################################
function logit {
  local msg="$1"
  echo "Grid Job pid($PID) $(date '+%Y%m%d %H%M%S'): $msg"
}
#--------------
function logerr {
  local msg="$1"
  logit "ERROR - $msg"
  #logit "JOB   FAILED: $(/bin/date)"
  logit "-------------------------------------------"
  #exit 1
}
#--------------
function log_environment {
  logit "Running as......... $(/usr/bin/id)"
  logit "Program............ $PGM"
  logit "PID................ $PID"
  logit "Hostname........... $(/bin/hostname -f)"
  logit "OSG_SITE_NAME...... $OSG_SITE_NAME"
  logit "HOME............... $HOME"
  logit "OSG_WN_TMP......... $OSG_WN_TMP  "
  logit "-------------------------------------------" 
  logit "All environmental variables:
$(env | sort)
"
}
#--------------
function log_glexec_conf {
  cfg=/etc/glexec/glexec.conf
  logit "#### glexec start ##################"
  if [ -e $cfg ];then
    logit "$(ls -l $cfg)"
    if [ -r $cfg ];then
      logit "$(cat $cfg)"
    else
      logit "WARNING: $cfg is not readable"
    fi
  else
    logit "WARNING: $cfg does not exist"
  fi
  logit "#### end glexec ###################"
}
#--------------
function log_running_jobs {
  logit "##### $(date) #############################"
  logit "##### RUNNING JOBS ###############"
  ps -ef |egrep "condor|procd|glexec|fgtest|$PID |$PPID " |egrep -v "^daemon|grep" |sed -e's/$/\n/'
}
#--------------
function log_timing_data {
  logit "#---- job timing output start ----"
  if [ ! -f "$timing" ];then
    logerr "file($timing) does not exist."
  fi
  #--- get last timing output ---
  while
    read line
  do
    logit "$line"
  done <$timing
  rm -f $timing
  logit "#---- job timing output end ----"
}
#--------------
function timing_loop {
  log_running_jobs
  start_time=$(date +'%s')
  last=$(date +'%s')
  elapsed=0
  while 
    [ $elapsed -le $mintime ]
  do 
    #--- create cpu/io ----
    local cycles=100
    local cnt=0
    while 
      [ $cnt -lt $cycles ]
    do
      echo "`date`" >$file
      cnt=$(($cnt + 1))
    done
    #-- determine elapsed time ---
    end_time=$(date +'%s')
    elapsed=$(($end_time - $start_time))
    #-- determine if running jobs to be listed ---
    now=$(date +'%s')
    if [ $(($now - $last)) -gt 300 ];then
      log_running_jobs
      last=$now
   fi
  done
  log_running_jobs
} 
#---------------
function capture_condor_logs {
  logit "######## glidein Condor logs start ##########"
  dir1=$(dirname $_CONDOR_SCRATCH_DIR)
  dir2=$dir1/..
  dir3=$dir1/../..
  dir4=$dir1/../../log
  for dir in $dir1 $dir2 $dir3 $dir4
  do
    logit " -------------------------------------------
PWD=$dir
$(ls -la $dir)
"
  done

  for log in $(ls $dir4/*Log)
  do
    logit " -------------------------------------------
LOG: $log 
$(cat $log)
"
  done
  logit "######## glidein Condor logs end ############"
} 
#---------------
function cleanup_files {
  if [ ! -f "$file" ];then
    logerr "file($file) does not exist."
  fi
  rm -f $file
  if [ -f "$file" ];then
    logerr "failed to clean up file($file)."
  fi
}
### MAIN ###################
PGM=$0
PID=$$
job_start=$(date '+%s')

#--- verify important Grid variables exist ---
if [ -z "$OSG_WN_TMP" ];then
  logerr "OSG_WN_TMP variable is empty"
fi
if [ ! -d "$OSG_WN_TMP" ];then
  logerr "OSG_WN_TMP directory($OSG_WN_TMP) does not exist"
fi

export mintime=2  #quick job by default for volume testing
if [ -n "$1" ];then
  export mintime=$(($1 * 60))
fi

logit "-------------------------------------------"
logit "JOB STARTED: $(/bin/date)"
log_environment 
log_glexec_conf

export file=$_CONDOR_SCRATCH_DIR/$(/usr/bin/whoami).tmpfile.$PID
export timing=$_CONDOR_SCRATCH_DIR/$(/usr/bin/whoami).timing.$PID
#--- execute to create cpu/io and for minimum time --
logit "Creating tmp file ($file) to consume CPU/Wall"
logit "Executing minimum $mintime seconds ($(($mintime/60)) minutes)"
touch $file
touch $timing
rslt=`ls -la $timing`
logit "before result of ls -la $timing is $rslt"
(time -p timing_loop) 2>$timing 
rslt=`ls -la $timing`
logit "after result of ls -la $timing is $rslt"
logit
#log_timing_data 
capture_condor_logs
cleanup_files 

job_end=$(date '+%s')
total_elapsed=$(($job_end -$job_start))
logit "Wall time: $(($total_elapsed/60)) minutes ($total_elapsed seconds)"
logit "-------------------------------------------"
logit "JOB   ENDED: $(/bin/date)"
exit 0
