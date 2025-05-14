The new `jobsub_api` allows users to import and use jobsub functionality programmatically through high-level functions that mimic the `jobsub_*` commands.  The main functions users will use are `jobsub_api.submit()` and `jobsub_api.q()`, similar to how users now mainly use `jobsub_submit` and `jobsub_q`.  For the most part, the function signatures will mirror the command-line options - for example, `jobsub_api.submit()` accepts an `f` argument that corresponds to the `-f` command line option, a `tar_file_name` argument that corresponds to the `--tar-file-name` option, etc.  Both `jobsub_api.submit()` and `jobsub_api.q()` will raise  `jobsub_api.JobsubAPIError`s if they fail.  Like the example below shows, users can catch that error to handle it as they see fit.

`jobsub_fetchlog` translates to a method on the returned class (`jobsub_api.SubmittedJob`) from `jobsub_api.submit()`.

## Coding Example

```python
 import sys
 sys.path.append('/opt/jobsub_lite/lib')
 import jobsub_api

 def fancy_api_demo():
    group = "fermilab"
    testdir = os.path.dirname(__file__)
    try:
        job1 = submit(
            group=group, executable=f"{testdir}/job_scripts/lookaround.sh", verbose=1
        )
        print(f"submitted job: {job1.id}")
        print(f"submit output:\n=-=-=-=-=\n {job1.submit_out}")
        print(f"\n=-=-=-=-=\n")

        qjobs = q(job1.id, group=group)
        for qjob in qjobs:
            print(f"saw job {qjob.id} status {str(qjob.status)} ")

        rs = job1.fetchlog(destdir="/tmp/test_fetch", verbose=1)
        print(f"fetchlog says: {rs}")
        sb = os.stat("/tmp/test_fetch/lookaround.sh")

        data = job1.q_long()
        print(f"after update, status: {str(job1.status)}")
        assert "ClusterId" in data
    except jobsub_api.JobsubAPIError as e:
        print(f"jobsub submit/q failure: {repr(e)}")
```

## Help on function q in module jobsub_api (some of these signatures may change prior to release):

 ```python
q(*jobids: str, devserver: bool = False, verbose: int = 0, **kwargs: str) -> List[jobsub_api.SubmittedJob]
```
Return list of SubmittedJob objects of running jobs

* Keyword Arguments:
    * devserver -- (bool) use development server
    * verbose -- (int) verbosity
    * group -- group/experiment to authenticate under
    * auth_methods -- comma sep list from token,proxy
    * global_pool -- alternate pool i.e. "dune"
    * role -- role to authenticate under
    * subgroup -- further authentication subgroup
    * constraint -- job limit constraint, see condor docs
    * name -- schedd name to use
    * user -- restrict to user's jobs
    * Remaining arguments are jobids to query

## Help on function submit in module jobsub_api (some of these signatures may change prior to release)

```python
submit(executable: str, exe_arguments: List[str] = [], lines: List[str] = [], env: Dict[str, str] = {}, **kwargs: str) -> jobsub_api.SubmittedJob
```

Submit a Condor job with jobsub_submit.  Takes a plethora of arguments
based on the jobsub_submit script arguents, see that documentation for more details.

- Booolean arguments:
	- dag -- executable is a dagnabbit dag file, not a script
	- mail_always  -- when to send mail
	- mail_on_error
	- mail_never
	- managed_token -- optimzie for managed tokens
	- n -- don't actually submit, just generate files
	- onsite -- restrict job to onsite
	- offsite -- restrict job to offsite
	- use_cvmfs_dropbox -- use cvmfs RCDS service for dropbox files
	- use_pnfs_dropbox -- use DCahe for dropbox files
- Options taking lists of strings
    - lines -- lines to append to job file
    - f -- input file to copy into job working directory
    - tar_file_name -- tarfile to send to job and unpack in $TAR_DIR_LOCAL
    - exe_arguments -- command-line arguments to give to  executable
- Options taking a dictionary
 - env environment variables and values to pass
    - d -- tag:destination string;  Writable directory `$CONDOR_DIR_<tag>` will exist on the execution node. After job completion, its contents will be moved to `<dir>`
- Options taking string values
	- executable -- executable to run
	- auth_methods -- comma separated list from toksn,proxy
	- blocklist -- comma separated list of sites to avoid
	- c -- condor requirements to append
	- cmtconfig -- cmt configuration (Minerva speceific)
	- cpu -- minimum cpu's to request
	- dataset_definition -- SAM dataset definition for project/DAG
	- dd_extra_dataset -- SAM extra datasaet definition to stage in start job
	- dd_percentage -- Percentage staging to require in start job
	- devserver -- use development schedd to submit
	- disk -- disk space tor equest, with units from  KB,MB,GB,TB
	- email_to -- email address for results units from s,m,h,d
	- generate_email_summary -- one mail for DAG jobs summary
	- G -- group / experiment name
	- global_pool -- global pool name if any (.ie. "dune")
	- gpu -- number of gpus  on nodes
	- i - experiment release directory
	- job_info -- script to call with jobid and command line upon submission
	- L -- log file name for job output
	- maxConcurrent -- maxumum number of jobs to run simultaneously
	- memory -- amount of memory to request allows suffixes from KB,MB,GB,TB
	- need_scope -- scopes needed in job auth tokens
	- need_storage_modify -- paths to ave storage:modif in auth token scope
	- N -- number of jobs to submit
	- no_env_cleanup -- do not clean environment in wrapper script
	- OS -- operating system to request, can be multiples comma separated
	- overwrite_condor_requirements -- requirements to replace standard ones
	- project_name -- name of SAM project to use in DAGS
	- resource_provides -- request specific resources
	- role -- token role to use
	- r -- experiment release version
	- singularity_image -- cvmfs path to singularity image for job
	- site -- comma separated list of sites to use
	- skip_check -- skip checks done by default from rcds
	- subgroup -- subgroup with role for permissions
	- tarball_exclusion_file -- file exculsions for tarfile generation
	- job_info -- script to call with jobid and command line upon submission
	- L -- log file name for job output
	- maxConcurrent -- maxumum number of jobs to run simultaneously
	- memory -- amount of memory to request allows suffixes from KB,MB,GB,TB
	- need_scope -- scopes needed in job auth tokens
	- need_storage_modify -- paths to ave storage:modif in auth token scope
	- N -- number of jobs to submit
	- no_env_cleanup -- do not clean environment in wrapper script
	- OS -- operating system to request, can be multiples comma separated
	- overwrite_condor_requirements -- requirements to replace standard ones
	- project_name -- name of SAM project to use in DAGS
	- resource_provides -- request specific resources
	- role -- token role to use
	- r -- experiment release version
	- singularity_image -- cvmfs path to singularity image for job
	- site -- comma separated list of sites to use
	- skip_check -- skip checks done by default from rcds
	- subgroup -- subgroup with role for permissions
	- tarball_exclusion_file -- file exculsions for tarfile generation
	- timeout -- end job if it runs longer than this units from ms,m,h,d
	- t -- experiment test-relesase directory
	- verbose -- verbosity, interger from 1 to 10

## Submitted Job Objects

`Job` objects  (existing in `condor.py`) have members
* id for jobids
* seq -- job sequence number / cluster_id
* cluster -- boolean whether we are a whole cluster n@schedd or job n.m@schedd
* proc -- process within cluster
* schedd -- schedd job was submitted to

`jobsub_api.SubmittedJob` objects add
* pool
* group
* role
* auth_methods
* submit_output (onlyt if the result of submit())
* owner  (if jobsub_q output or q() methods called)
* submitted (datetime.datetime) (default: `None`)
* runtime (datetime.timedelta) (default: `None`)
* status (htcondor.JobStatus) (default: `None`)
* prio
* size
* command

as well as methods:
* hold()
* release()
* rm()
* fetchlog( destdir, condor=False)
* q()  (update owner, status, etc. with jobsub_q)
* q_long() (...and return --long info as dictionary)
* q_analyze() (return jobsub_q --better-analyze output)
* wait() (run q() periodically until status COMPLETED, HELD, or REMOVED.)
* find_dag_jobs() -- assuming we're a dagman job, find list of jobs the dagman launched, attach as job.dagjobs
