universe           = vanilla
executable         = {{full_executable}}
arguments          = --disk {{disk}}  -d {{d}}  --email-to {{email_to}} {% for item in environment%} -e {{item}}{%endfor%} --expected-lifetime {{expected_lifetime}}  {% for item in input_file %} -f {{item}}{%endfor%} {%if generate_email_summary%}--generate-email-summary  {{generate_email_summary}}{%endif%} -L {{L}} {%for l in lines%} -l  {{l}}{%endfor%} -Q{%if mail_on_error%} --mail_on_error{%endif%} {%if mail_always%} --mail_always{%endif%} --memory {{memory}} -N {{N}} --OS {{OS}}  --overwrite_condor_requirements {{overwrite_condor_requirements}} --resource-provides {{resource_provides}} --site  {{site}} --subgroup  {{subgroup}}  --tar_file_name  {{tar_file_name}} --timeout {{timeout}} --verbose {{verbose}} {{executable_basename}} {{exe_arguments|join(" ")}}

{% set dir %}/fife/local/scratch/uploads/{{group}}/{{user}}/{{date}}.{{uuid}}{% endset %}
{% set filebase %}{{dir}}/{{executable_basename}}{{date}}{{uuid}}cluster.$(Cluster).$(Process){% endset %}

output             = {{filebase}}.out
error              = {{filebase}}.err
log                = {{filebase}}.log
environment        = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP={{dir}};CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};JOBSUBJOBID=$(CLUSTER).$(PROCESS)@{{schedd}};EXPERIMENT={{group}};{{env}}
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
{%if blacklist %}
+Blacklist_Sites = "{{blacklist}}"
{% endif %}
+GeneratedBy ="{{version}} {{schedd}}"
{{resource_provides|join("\n+DESIRED_")}}
{{lines|join("\n+")}}
requirements  = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2  && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model))) && {{append_condor_requriments}}

queue {{N}}
