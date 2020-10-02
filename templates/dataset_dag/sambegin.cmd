universe           = vanilla
executable         = {{submitdir}}/sambegin.sh
arguments          = 

{% set filebase %}{{outdir}}/sambegin{{date}}{{uuid}}cluster.$(Cluster).$(Process){% endset %}
output             = {{filebase}}.out
error              = {{filebase}}.err
log                = {{filebase}}.log
environment        = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP={{dir}};CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};JOBSUBJOBID=$(CLUSTER).$(PROCESS)@{{schedd}};EXPERIMENT={{group}};{{environment|join(';')}}
rank                  = Mips / 2 + Memory
notification  = Error
+RUN_ON_HEADNODE= True
transfer_executable     = True
when_to_transfer_output = ON_EXIT_OR_EVICT
+JobsubClientDN="/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab/CN=poms-pomsgpvm01.fnal.gov"
+JobsubClientIpAddress="131.225.80.97"
+Owner="mengel"
+JobsubServerVersion="1.3.1.1"
+JobsubClientVersion="1.3"
+JobsubClientKerberosPrincipal="poms/cd/fermicloud045.fnal.gov@FNAL.GOV"
+FIFE_CATEGORIES="POMS_TASK_ID_1391,POMS_CAMPAIGN_ID_1"
+POMS_TASK_ID=1391
+POMS_CAMPAIGN_ID=1
+POMS_LAUNCHER=mengel
+POMS_CAMPAIGN_NAME="fake_demo_v1.0__w/chars__f_eg_v1.0_-_w/chars"
+POMS4_CAMPAIGN_STAGE_ID=1
+POMS4_CAMPAIGN_STAGE_NAME="f_eg_v1.0_-_w/chars"
+POMS4_CAMPAIGN_ID=890
+POMS4_CAMPAIGN_NAME="fake_demo_v1.0__w/chars"
+POMS4_SUBMISSION_ID=1391
+POMS4_CAMPAIGN_TYPE=
+POMS4_TEST_LAUNCH=False
+JOB_EXPECTED_MAX_LIFETIME = 7200
+JobsubParentJobId = "$(DAGManJobId).0@jobsub03.fnal.gov" 
+Jobsub_Group="fermilab"
notify_user = mengel@fnal.gov
x509userproxy = /tmp/x509up_voms_{{group}}_{{role}}_{{uid}}

+AccountingGroup = "group_fermilab.mengel"
+JobsubJobId="$(CLUSTER).$(PROCESS)@jobsub03.fnal.gov"
+JobsubJobSection = "7"

+Drain = False
+GeneratedBy ="NO_UPS_VERSION jobsub03.fnal.gov"
+DESIRED_usage_model = "OPPORTUNISTIC,DEDICATED"
request_memory = 100
requirements  = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2  && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model))) {%if append_condor_requirements %} && {{append_condor_requriments}} {%endif%}
queue 1
