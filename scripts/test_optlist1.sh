
options_with_values="
    --append_condor_requirements
    --blocklist
    --cpu
    --dataset_definition
    --disk
    -d
    --email-to
    -e
    --expected-lifetime
    -f
    -G
    -L
    -l
    --memory
    -N
    --OS
    --overwrite_condor_requirements
    --resource-provides
    --role
    --site
    --subgroup
    --timeout
    "

out=/tmp/out$$
jobsub_out=/tmp/jobsub_out$$
touch $out
sc=0
fc=0

for opt in $options_with_values
do
    echo "Test $opt ------------------------- " >> $out
    val=13579

    # special case for -e, needs an environment variable
    if [ x$opt == x-e ]
    then
       val=k$val
       export $val=junk
    fi

    if jobsub_submit --nosubmit $opt $val file:///usr/bin/printenv > $jobsub_out 2>&1
    then
	subfile=`tail -2 $jobsub_out | head -1`
	subdir=`dirname "$subfile"`
	if grep "$val" $subdir/* > /tmp/go.log 2>/dev/null
	then
	    printf "."
	    sc=$((sc + 1))
	    echo "test $opt SUCCEEDED." >> $out
	else
	    printf "F"
	    echo "test $opt FAILED:" >> $out
	    echo "subdir was '$subdir'" >> $out
	    echo "subfile was '$subfile'" >> $out
	    cat $jobsub_out >> $out
	    fc=$((fc + 1))
	fi
    else
        printf "N"
        echo "test $opt NO_SUBMIT_FILE." >> $out
        continue
    fi
done
printf "\n"
cat $out
echo "Success: $sc Failed: $fc"
