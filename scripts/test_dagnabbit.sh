
export SUBMIT_FLAGS="--memory 200MB -G fermilab --resource-provides=usage_model=OPPORTUNISTIC,DEDICATED"
../bin/jobsub_submit --devserver --group fermilab --dag ../../test/client/jobsubDagTest/dagTest
