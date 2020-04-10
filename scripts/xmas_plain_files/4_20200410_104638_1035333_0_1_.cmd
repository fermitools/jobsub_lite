universe          = vanilla
executable        = /fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059/4_20200410_104638_1035333_0_1_wrap.sh
arguments         =  --disk  100M  -d  D  --email-to  mengel@fnal.gov  -e  FRED  -e  JOE=5  --expected-lifetime  567  -f  input_1.txt  -f  input_2.txt  --generate-email-summary  1  -L  /tmp/submit.log  -l  +apple=1  -l  +orange=2  -Q  --mail_on_error  --mail_always  --maxConcurrent  10  --memory  MEMORY  -N  2  --OS  sl7  --overwrite_condor_requirements  abc==2  --resource-provides  usage_model=OPPORTUNISTIC,DEDICATED  --site  Fermigrid  --subgroup  Silly  --tar_file_name  tardir:/tmp/stuff  --timeout  TIMEOUT  3500  1  --verbose  1  /fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059/printenv 
output                = /fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059/4_20200410_104638_1035333_0_1_cluster.$(Cluster).$(Process).out
error                 = /fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059/4_20200410_104638_1035333_0_1_cluster.$(Cluster).$(Process).err
log                   = /fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059/4_20200410_104638_1035333_0_1_.log
environment   = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP=/fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059;CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER=mengel;IFDH_BASE_URI=http://samweb.fnal.gov:8480/sam/fermilab/api;JOBSUBJOBID=$(CLUSTER).$(PROCESS)@jobsub02.fnal.gov;EXPERIMENT=fermilab
rank                  = Mips / 2 + Memory
job_lease_duration = 3600
notification = Never
when_to_transfer_output = ON_EXIT_OR_EVICT
transfer_output                 = True
transfer_output_files = .empty_file
transfer_error                  = True
transfer_executable         = True
transfer_input_files = /fife/local/scratch/uploads/fermilab/mengel/2020-04-10_104637.797920_1059/printenv
+JobsubClientDN="/DC=org/DC=cilogon/C=US/O=Fermi National Accelerator Laboratory/OU=People/CN=Marc Mengel/CN=UID:mengel"
+JobsubClientIpAddress="131.225.80.97"
+Owner="mengel"
+JobsubServerVersion="1.3.1.1"
+JobsubClientVersion="1.3.1"
+JobsubClientKerberosPrincipal="mengel@FNAL.GOV"
+JOB_EXPECTED_MAX_LIFETIME = 28800
notify_user = mengel@fnal.gov
x509userproxy = /var/lib/jobsub/creds/proxies/fermilab/x509cc_mengel_Analysis
+AccountingGroup = "group_fermilab.mengel"
+Jobsub_Group="fermilab"
+JobsubJobId="$(CLUSTER).$(PROCESS)@jobsub02.fnal.gov"
+Drain = False
+Blacklist_Sites = "FZU"
+GeneratedBy ="NO_UPS_VERSION jobsub02.fnal.gov"
request_cpus = 123
requirements  = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2 && ((isUndefined(target.GLIDEIN_Site) == FALSE) && (stringListIMember(target.GLIDEIN_Site,my.Blacklist_Sites) == FALSE)) && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && xyz==1 


queue 1