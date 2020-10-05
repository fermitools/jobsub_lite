
options_with_values="
    --append_condor_requirements
    --blacklist
    --cpu
    --dag
    --dataset_definition
    --debug
    --disk
    -d
    --email-to
    -e
    --expected-lifetime
    -f
    -G
    -L
    -l
    --maxConcurrent
    --memory
    -N
    --OS
    --overwrite_condor_requirements
    --resource-provides
    --role
    --site
    --subgroup
    --tar_file_name
    --tarball-exclusion-file
    --timeout
    --use-cvmfs-dropbox
    --verbose
    "

out=/tmp/out$$
jobsub_out=/tmp/jobsub_out$$
touch $out
sc=0
fc=0
for opt in $options_with_values
do
    val=13579
    subfile=`jobsub_submit --nosubmit $opt $val file:///usr/bin/printenv 2>&1 | tee $jobsub_out | tail -2`
    subdir=`dirname $subfile`
    if [ "$subdir" == '.' ]
    then
        printf "N"
        echo "test $opt NO_SUBMIT_FILE." >> $out
        continue
    fi
    if grep $val $subdir/* > /tmp/go.log
    then
        printf "."   
        sc=$((sc + 1))
        echo "test $opt SUCCEEDED." >> $out
    else
        printf "F" 
        echo "test $opt FAILED:" >> $out
        cat $jobsub_out >> $out
        fc=$((fc + 1))
    fi
done
printf "\n"
echo "Success: $sc Failed: $fc"
