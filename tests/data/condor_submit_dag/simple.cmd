
# generated by jobsub_lite
# debug
universe           = vanilla
executable         = simple.sh
arguments          = --find_setups --prescript-unquote echo%20JOBSUBJOBSECTION%20is%20%24%7BJOBSUBJOBSECTION%7D --setup-unquote hypotcode%20v1_1 --setup-unquote ifdhc%20v2_7_2%2C%20ifdhc_config%20v2_6_15 --self_destruct_timer 700 --debug --getconfig --limit 1 --appvers v1_1 --metadata_extractor hypot_metadata_extractor --addoutput gen.troot --rename unique --dest /pnfs/fermilab/users/$ENV(USER)/dropbox --add_location --declare_metadata --addoutput1 hist_gen.troot --rename1 unique --dest1 /pnfs/fermilab/users/$ENV(USER)/dropbox --add_location1 --declare_metadata1 --exe hypot.exe -- -o gen.troot -c hist_gen.troot

output             = fife_wrap2023_12_18_11225571a1aea7-4417-446c-920c-d3042a8f2b4bcluster.$(Cluster).$(Process).out
error              = fife_wrap2023_12_18_11225571a1aea7-4417-446c-920c-d3042a8f2b4bcluster.$(Cluster).$(Process).err
log                = fife_wrap2023_12_18_11225571a1aea7-4417-446c-920c-d3042a8f2b4bcluster.$(Cluster).$(Process).log


TRACEPARENT="00-14999afacbfba68c7f37f4d7008b3ec7-4a5c72262efc091f-01"
+TraceParent=$(TRACEPARENT)

getenv             = SAM_PROJECT,USER,DN
environment        = CM1=$(CM1);CM2=$(CM2);CLUSTER=$(Cluster);PROCESS=$(Process);JOBSUBJOBSECTION=$(JOBSUBJOBSECTION);CONDOR_TMP=/home/$ENV(USER)/.cache/jobsub_lite/js_2023_12_18_112255_71a1aea7-4417-446c-920c-d3042a8f2b4b;BEARER_TOKEN_FILE=.condor_creds/fermilab_b355f5a23c.use;CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER=$ENV(USER);JOBSUBJOBID=$(CLUSTER).$(PROCESS)@jobsubdevgpvm01.fnal.gov;EXPERIMENT=fermilab;TRACEPARENT=00-14999afacbfba68c7f37f4d7008b3ec7-4a5c72262efc091f-01;EXPERIMENT=samdev;IFDH_DEBUG=1;IFDH_VERSION=v2_6_10;IFDH_TOKEN_ENABLE=1;IFDH_PROXY_ENABLE=0;SAM_EXPERIMENT=samdev;SAM_GROUP=samdev;SAM_STATION=samdev;IFDH_CP_MAXRETRIES=2;VERSION=v1_1;SAM_DATASET=gen_cfg;SAM_USER=$ENV(USER)
rank               = Mips / 2 + Memory
job_lease_duration = 3600
transfer_output    = True
transfer_error     = True
transfer_executable= True
transfer_input_files = fife_wrap
# if transfer_output_files is not explicitly set, condor will transfer ALL the files the job touches (unless in grid universe)
transfer_output_files = .empty_file
when_to_transfer_output = ON_EXIT_OR_EVICT

request_memory = 500.0
request_disk = 102400.0KB

+JobsubClientDN="$ENV(DN)"
+JobsubClientIpAddress="131.225.60.169"
+JobsubServerVersion="jobsub_lite-v1.5"
+JobsubClientVersion="jobsub_lite-v1.5"
+JobsubClientKerberosPrincipal="$ENV(USER)@FNAL.GOV"
+JOB_EXPECTED_MAX_LIFETIME = 7200.0
notify_user = "$ENV(USER)@fnal.gov"
notification = Never

# set command to user executable for jobsub_q
+JobsubCmd = "fife_wrap"


+AccountingGroup = "group_fermilab.$ENV(USER)"


+Jobsub_Group="fermilab"
+JobsubJobId="$(CLUSTER).$(PROCESS)@jobsubdevgpvm01.fnal.gov"
+JobsubOutputURL="https://fndcadoor.fnal.gov:2880/fermigrid/jobsub/jobs/2023_12_18/71a1aea7-4417-446c-920c-d3042a8f2b4b"
+JobsubUUID="71a1aea7-4417-446c-920c-d3042a8f2b4b"
+Drain = False
# default for remote submits is to keep completed jobs in the queue for 10 days
+LeaveJobInQueue = False


+DESIRED_SITES = ""


+GeneratedBy ="jobsub_lite-v1.5 jobsubdevgpvm01.fnal.gov"

+DESIRED_usage_model = "DEDICATED,OPPORTUNISTIC,OFFSITE"




requirements = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2 && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model)))


+SingularityImage="/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest"


#
# this is supposed to get us output even if jobs are held(?)
#
+SpoolOnEvict = false
#
#
#

# Credentials


use_oauth_services = fermilab

fermilab_oauth_permissions_b355f5a23c = " compute.read compute.create compute.cancel compute.modify storage.read:/fermilab/users/$ENV(USER) storage.create:/fermilab/users/$ENV(USER) storage.create:/fermigrid/jobsub/jobs "





+x509userproxy = "x509up_fermilab_Analysis_$ENV(UID)"

delegate_job_GSI_credentials_lifetime = 0


queue 1
