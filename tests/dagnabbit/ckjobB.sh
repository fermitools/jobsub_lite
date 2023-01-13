#!/bin/bash

RETURN=${1}
LogFile=${2}_${3}.log
JOBID=${4}
echo "@: ${@}" >> ${LogFile} 2>&1

ckjobs() {
    echo -e "\n*** DATE: \c"
    date

    echo "JOBID: ${JOBID}"
    echo "RETURN: ${RETURN}"

    if [[ ${RETURN} -ne 0 ]]; then
        echo -e "\n\n*** job failed exit code: ${RETURN} ... exiting\n\n"
        exit ${RETURN}
    fi

    echo "uname: `uname -a`"

    echo "hostname: `hostname`"

    echo "pwd: $(pwd)"

    echo -e "ls -lh:\n$(ls -lh)"

    echo -e "\n*** DATE: \c"
    date
}

ckjobs >> ${LogFile} 2>&1
