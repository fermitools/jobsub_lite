universe           = vanilla
executable         = {{full_executable}}
arguments          = {{args|join(" ")}}
{% set dir %}/fife/local/scratch/uploads/{{group}}/{{user}}/{{date}}.{{uuid}}{% endset %}
{%set filebase %}{{dir}}/{{dir}}{{executable_basename}}{{datestamp}}{{uuid}}cluster.$(Cluster).$(Process){% endset %}
output             = {{filebase}}.out
error              = {{filebase}}.err
log                = {{filebase}}.log
environment        = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP={{dir}};CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};{{env}}
rank               = Mips / 2 + Memory
job_lease_duration = 3600
notification       = Never
transfer_output    = True
transfer_error     = True
transfer_executable= True
transfer_input_files = {{dir}}/{{executable_basename}}
when_to_transfer_output = ON_EXIT_OR_EVICT
transfer_output_files = .empty_file
{%if OS %}
+DesiredOS={{OS}}
{%endif%}
+JobsubClientDN="{{clientdn}}
+JobsubClientIpAddress="{{ipaddr}}"
+Owner="{{user}}"
+JobsubServerVersion="{{jobsub_version}}"
+JobsubClientVersion="{{jobsub_version}}"
+JobsubClientKerberosPrincipal="{{kerberosprincipal}}"
+JOB_EXPECTED_MAX_LIFETIME = {{expected_lifetime}}
notify_user = {{notify_user}}
x509userproxy = /var/lib/jobsub/creds/proxies/{{group}}/x509cc_{{user}}_{{role}}
+AccountingGroup = "group_{{group}}.{{user}}"
+Jobsub_Group="{{group}}"
+JobsubJobId="$(CLUSTER).$(PROCESS)@{{schedd}}"
+Drain = False
+GeneratedBy ="{{version}} {{schedd}}"
{{resource_provides|join("\n")}}
requirements  = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2  && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model)))

queue {{N}}
