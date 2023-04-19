# generated by jobsub_lite
# {%if debug is defined and debug %}debug{%endif%}
universe           = vanilla
executable         = samend.sh
arguments          =

{% set filebase %}samend.$(Cluster).$(Process){% endset %}
output             = {{filebase}}.out
error              = {{filebase}}.err
log                = {{filebase}}.log
environment        = CLUSTER=$(Cluster);PROCESS=$(Process);CONDOR_TMP={{outdir}};BEARER_TOKEN_FILE=.condor_creds/{{group}}.use;CONDOR_EXEC=/tmp;DAGMANJOBID=$(DAGManJobId);GRID_USER={{user}};JOBSUBJOBID=$(CLUSTER).$(PROCESS)@{{schedd}};EXPERIMENT={{group}};{{environment|join(';')}}
rank                  = Mips / 2 + Memory
notification  = Error
+RUN_ON_HEADNODE= True
transfer_executable     = True
rank               = Mips / 2 + Memory
job_lease_duration = 3600
transfer_error     = True
transfer_executable= True
transfer_output_files=.empty_file
when_to_transfer_output = ON_EXIT_OR_EVICT
request_memory = 100mb
{%if     OS is defined and OS %}+DesiredOS="{{OS}}"{%endif%}
+JobsubClientDN="{{clientdn}}"
+JobsubClientIpAddress="{{ipaddr}}"
+JobsubServerVersion="{{jobsub_version}}"
+JobsubClientVersion="{{jobsub_version}}"
+JobsubClientKerberosPrincipal="{{kerberos_principal}}"
+JOB_EXPECTED_MAX_LIFETIME = {{expected_lifetime}}
+AccountingGroup = "group_{{group}}.{{user}}"
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
{%if blacklist is defined and blacklist  %}
+Blacklist_Sites = "{{blacklist}}"
{% endif %}
+GeneratedBy ="{{jobsub_version}} {{schedd}}"
{%if usage_model is defined and usage_model  %}
+DESIRED_usage_model = "{{usage_model}}"
{% endif %}
{%if resource_provides_quoted%}
+DESIRED_{{resource_provides_quoted|join("\n+DESIRED_")}}
{% endif %}
{%if skip_check is defined and skip_check%}
+JobsubSkipChecks = "{{skip_check|join(",")}}"
{%endif%}
{{lines|join("\n")}}
requirements = target.machine =!= MachineAttrMachine1 && target.machine =!= MachineAttrMachine2 && (isUndefined(DesiredOS) || stringListsIntersect(toUpper(DesiredOS),IFOS_installed)) && (stringListsIntersect(toUpper(target.HAS_usage_model), toUpper(my.DESIRED_usage_model))){%if site is defined and site != '' %} && ((isUndefined(target.GLIDEIN_Site) == FALSE) && (stringListIMember(target.GLIDEIN_Site,my.DESIRED_Sites))){%endif%}{%if append_condor_requirements is defined and append_condor_requirements %} && {{append_condor_requirements}}{%endif%}

{% if no_singularity is false %}
+SingularityImage="{{singularity_image}}"
{% endif %}

# Credentials
{% if role is defined and role and role != 'Analysis' %}
use_oauth_services = {{group}}_{{role | lower}}
#{{group}}_{{role | lower}}_oauth_permissions = "{{job_scope}}"
{% else %}
use_oauth_services = {{group}}
#{{group}}_oauth_permissions = "{{job_scope}}"
{% endif %}
{% if role is defined %}
+x509userproxy = "{{proxy|basename}}"
delegate_job_GSI_credentials_lifetime = 0
{% endif %}

queue 1
