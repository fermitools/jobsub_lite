universe           = vanilla
executable        = {{submitdir}}/samend.sh
arguments          = {{exe_arguments|join(" ")}}

{% set filebase %}{{outdir}}/{{executable_basename}}{{date}}{{uuid}}cluster.$(Cluster).$(Process){% endset %}
output             = {{filebase}}.out
error              = {{filebase}}.err
log                = {{filebase}}.log
environment        = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP={{dir}};CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};JOBSUBJOBID=$(CLUSTER).$(PROCESS)@{{schedd}};EXPERIMENT={{group}};{{environment|join(';')}}
rank                  = Mips / 2 + Memory
notification  = Error
+RUN_ON_HEADNODE= True
transfer_executable     = True
rank               = Mips / 2 + Memory
job_lease_duration = 3600
notification       = Never
transfer_output    = True
transfer_error     = True
transfer_executable= True
transfer_input_files = {{dir}}/{{executable_basename}}
when_to_transfer_output = ON_EXIT_OR_EVICT
transfer_output_files = .empty_file
{%if    cpu %}request_cpus = {{cpu}}{%endif%}
{%if memory %}request_memory = {{memory}}{%endif%}
{%if   disk %}request_disk = {{disk}}{%endif%}
{%if     OS %}+DesiredOS={{OS}}{%endif%}
+JobsubClientDN="{{clientdn}}"
+JobsubClientIpAddress="{{ipaddr}}"
+Owner="{{user}}"
+JobsubServerVersion="{{jobsub_version}}"
+JobsubClientVersion="{{jobsub_version}}"
+JobsubClientKerberosPrincipal="{{kerberosprincipal}}"
+JOB_EXPECTED_MAX_LIFETIME = {{expected_lifetime}}
notify_user = {{notify_user}}
x509userproxy = /tmp/x509up_voms_{{group}}_{{role}}_{{uid}}
+AccountingGroup = "group_{{group}}.{{user}}"
+Jobsub_Group="{{group}}"
+JobsubJobId="$(CLUSTER).$(PROCESS)@{{schedd}}"
+Drain = False
{%if blacklist %}
+Blacklist_Sites = "{{blacklist}}"
{% endif %}
+GeneratedBy ="{{version}} {{schedd}}"
{{resource_provides_quoted|join("\n+DESIRED_")}}
{{lines|join("\n+")}}
requirements  = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2  && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model))) {%if append_condor_requirements %} && {{append_condor_requriments}} {%endif%}

