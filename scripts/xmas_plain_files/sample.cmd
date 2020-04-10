universe               = vanilla
executable             = {{wrap_sh}}
arguments              = --disk {{disk}}  -d {{d}}  --email-to {{email_to}} {% for item in environment%} -e {{item} {%endfor%}  --expected-lifetime  {{expected-lifetime}}  {% for item in file %} -f {{item}} {%enfor%} {%if generate-email-summary%}--generate-email-summary  {{generate-email-summary}} {%endif%}  -L  {{L]}  {%for l in lines%} -l  {{l}} {%endfor%}  -Q  {%if mail_on_error%}--mail_on_error{%endif%} {%if mail_always%} --mail_always {%endif%} --memory {%memory%}  -N {{N}}  --OS  {{OS}}  --overwrite_condor_requirements {{overwrite_condor_requirements}} abc==2  --resource-provides {{resource_provides}} --site  {{site}} --subgroup  {{subgroup}}  --tar_file_name  {{tar_file_name}} --timeout {{timeout}} --verbose {{verbose}} {{executable}
output                 = /fife/local/scratch/uploads/{{group}}/{{user}}/{{datestamp}}{{uuid}}/{{datestamp}}{{uuid}}_cluster.$(Cluster).$(Process).out
error                  = /fife/local/scratch/uploads/{{group}}/{{user}}/{{datestamp}}{{uuid}}/{{datestamp}}{{uuid}}_cluster.$(Cluster).$(Process).err
log                    = /fife/local/scratch/uploads/{{group}}/{{user}}/{{datestamp}}{{uuid}}/{{datestamp}}{{uuid}}_cluster.$(Cluster).$(Process).log
environment            = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP=/fife/local/scratch/uploads/{{group}}/{{user}}/{{datestamp}}{{uuid}};CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};IFDH_BASE_URI=http://samweb.fnal.gov:8480/sam/{{group}}/api;JOBSUBJOBID=$(CLUSTER).$(PROCESS)@jobsub02.fnal.gov;EXPERIMENT={{group}}
rank                   = Mips / 2 + Memory
job_lease_duration     = 3600
notification           = Never
when_to_transfer_output= ON_EXIT_OR_EVICT
transfer_output        = True
transfer_output_files  = .empty_file
transfer_error         = True
transfer_executable    = True
transfer_input_files   = {{executable}}
+JobsubClientDN        ="{{clientdn}}"
+JobsubClientIpAddress ="{{ipaddr}}"
+Owner                 ="{{user}}"
+JobsubServerVersion="lite"
+JobsubClientVersion="{{version}}"
+JobsubClientKerberosPrincipal="{{principal}}"
+JOB_EXPECTED_MAX_LIFETIME = {{expected_lifetime}}
notify_user = {{notify}}
x509userproxy = /var/lib/jobsub/creds/proxies/{{group}}/x509cc_{{user}}_{{role}}
+AccountingGroup = "group_{{group}}.{{user}}"
+Jobsub_Group="{{group}}"
+JobsubJobId="$(CLUSTER).$(PROCESS)@{{schedd}}"
+Drain = False
+Blacklist_Sites = "{{blacklist}}"
+GeneratedBy ="{{version}} {{schedd}}"
request_cpus = {{cpu}}
requirements  = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2 && ((isUndefined(target.GLIDEIN_Site) == FALSE) && (stringListIMember(target.GLIDEIN_Site,my.Blacklist_Sites) == FALSE)) && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && {{append_condor_requriments}}

queue {{N}}
