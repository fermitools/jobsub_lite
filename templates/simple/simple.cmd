
# generated by jobsub_lite
# {%if debug is defined and debug %}debug{%endif%}
universe           = vanilla
executable         = {{script_name|default('simple.sh')}}
arguments          = {{exe_arguments|join(" ")}}
{% set filebase %}{{executable|basename}}{{datetime}}{{uuid}}cluster.$(Cluster).$(Process){% endset %}
output             = {{filebase}}.out
error              = {{filebase}}.err
log                = {{filebase}}.log

{%if not ( is_dag is defined and is_dag ) %}
JOBSUBJOBSECTION=$(Process)
{%endif%}
TRACEPARENT="{{traceparent}}"
+TraceParent=$(TRACEPARENT)

environment        = CM1=$(CM1);CM2=$(CM2);CLUSTER=$(Cluster);PROCESS=$(Process);JOBSUBJOBSECTION=$(JOBSUBJOBSECTION);CONDOR_TMP={{outdir}};{% if token is defined and token %}BEARER_TOKEN_FILE=.condor_creds/{% if role is defined and role and role != 'Analysis' %}{{group}}_{{role | lower}}_{{oauth_handle}}.use{%else%}{{group}}_{{oauth_handle}}.use{%endif%}{% endif %};CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};JOBSUBJOBID=$(CLUSTER).$(PROCESS)@{{schedd}};EXPERIMENT={{group}};TRACEPARENT={{traceparent}};{{environment|join(';')}}
rank               = Mips / 2 + Memory
job_lease_duration = 3600
transfer_output    = True
transfer_error     = True
transfer_executable= True
transfer_input_files = {{executable|basename}}
# if transfer_output_files is not explicitly set, condor will transfer ALL the files the job touches (unless in grid universe)
transfer_output_files = .empty_file
when_to_transfer_output = ON_EXIT_OR_EVICT
{%if    cpu is defined and cpu %}request_cpus = {{cpu}}{%endif%}
{%if    gpu is defined and gpu %}
request_GPUs = {{gpu}}
+RequestGPUs = {{gpu}}
{%endif%}
{%if memory is defined and memory %}request_memory = {{memory}}{%endif%}
{%if   disk is defined and disk %}request_disk = {{disk}}KB{%endif%}
{%if     OS is defined and OS %}+DesiredOS="{{OS}}"{%endif%}
{% if clientdn is defined and clientdn %}+JobsubClientDN="{{clientdn}}"{% endif %}
+JobsubClientIpAddress="{{ipaddr}}"
+JobsubServerVersion="{{jobsub_version}}"
+JobsubClientVersion="{{jobsub_version}}"
+JobsubClientKerberosPrincipal="{{kerberos_principal}}"
+JOB_EXPECTED_MAX_LIFETIME = {{expected_lifetime}}
notify_user = "{{email_to}}"
notification = {{mail}}

# set command to user executable for jobsub_q
+JobsubCmd = "{{executable|basename}}"

{% if subgroup is defined and subgroup %}
+AccountingGroup = "group_{{group}}.{{subgroup}}.{{user}}"
{% else %}
+AccountingGroup = "group_{{group}}.{{user}}"
{% endif %}

+Jobsub_Group="{{group}}"
+JobsubJobId="$(CLUSTER).$(PROCESS)@{{schedd}}"
+JobsubOutputURL="{{outurl}}"
+JobsubUUID="{{uuid}}"
+Drain = False
# default for remote submits is to keep completed jobs in the queue for 10 days
+LeaveJobInQueue = False

{% if site is defined and site != 'LOCAL' %}
+DESIRED_SITES = "{{site}}"
{% endif %}
{%if blocklist is defined and blocklist  %}
+Blacklist_Sites = "{{blocklist}}"
{% endif %}
+GeneratedBy ="{{jobsub_version}} {{schedd}}"
{%if usage_model is defined and usage_model  %}
+DESIRED_usage_model = "{{usage_model}}"
{% endif %}
{% if skip_check is defined and skip_check %}
+JobsubSkipChecks = "{{skip_check|join(",")}}"
{% endif %}
{%if resource_provides_quoted%}
+DESIRED_{{resource_provides_quoted|join("\n+DESIRED_")}}
{% endif %}
{{lines|join("\n")}}
requirements = {%if overwrite_requirements is defined and overwrite_requirements %}{{overwrite_requirements}}{%else%}target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2 && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model))){%if site is defined and site != '' %} && ((isUndefined(target.GLIDEIN_Site) == FALSE) && (stringListIMember(target.GLIDEIN_Site,my.DESIRED_Sites))){%endif%}{%if blocklist is defined and blocklist != '' %} && ((isUndefined(target.GLIDEIN_Site) == FALSE) && (!stringListIMember(target.GLIDEIN_Site,my.Blacklist_Sites))){%endif%}{%endif%}{% if append_condor_requirements is defined and append_condor_requirements != [] %} && {{append_condor_requirements|join(" && ")}}{%endif%}

{% if no_singularity is false %}
+SingularityImage="{{singularity_image}}"
{% endif %}

#
# this is supposed to get us output even if jobs are held(?)
#
+SpoolOnEvict = false
#
#
#

# Credentials
{% if token is defined and token %}
{% if role is defined and role != 'Analysis' %}
use_oauth_services = {{group}}_{{role | lower}}
{% if job_scope is defined and job_scope %}
{{group}}_{{role | lower}}_oauth_permissions_{{oauth_handle}} = " {{job_scope}} "
{% endif %}
{% else %}
use_oauth_services = {{group}}
{% if job_scope is defined and job_scope %}
{{group}}_oauth_permissions_{{oauth_handle}} = " {{job_scope}} "
{% endif %}
{% endif %}
{% endif %}
{% if role is defined and proxy is defined and proxy %}
{% if is_dag|default(False) %}
+x509userproxy = "{{proxy|basename}}"
{% else %}
+x509userproxy = "{{proxy}}"
{% endif %}
delegate_job_GSI_credentials_lifetime = 0
{% endif %}

queue {{N}}
