#!/bin/bash

LogFile=${1}_${2}.log
JOBID=${3}
echo "@: ${@}" >> ${LogFile} 2>&1

initjobs() {
    echo -e "\n*** DATE: \c"
    date

    echo "JOBID: ${JOBID}"

    echo "uname: `uname -a`"

    echo "hostname: `hostname`"

    echo "pwd: $(pwd)"

    echo -e "ls -lh:\n$(ls -lh)"

    echo -e "\n*** DATE: \c"
    date
}

initjobs >> ${LogFile} 2>&1
