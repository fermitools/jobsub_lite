[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/shreyb/jobsub_lite/master.svg)](https://results.pre-commit.ci/latest/github/shreyb/jobsub_lite/master)

#  `jobsub_lite` Overview

jobsub_lite is a wrapper for Condor job submission, intended
to be backwards compatible with the actively used options of
the past Fermilab jobsub tools, while being smaller and easier
to maintain, and handling new requirements (i.e SciTokens
authentication, etc.)

The basic design of jobsub_lite is straightforward. It will:

* obtain credentials (using cigetcert, htgettoken, etc.)
* parse command line arguments into a (Python) dictionary
* optionally upload tarballs to the fast cvmfs distribution service
* add other data to the dictionary from the environment, etc.
* render (Jinja) templates with info from said dictionary to generate:
        - condor .cmd file(s)
        - job wrapper script(s)
        - condor dagman .dag files (in some cases)
* use the Condor python bindings and command line tools to submit the above

There is also a simplified dagnabbit parser (again for past jobsub DAG tools compatbilit) that reuses the same command line parser to generate .cmd and .sh files for each stage in the DAG.

## Credentials

This version of jobsub is expected to deal with SciTokens credentials; and will use the new ifdhc getToken call to fetch them, which in turn will call the htgettoken utility.  Current thinking is that production accounts will have special production tokens pushed to them, and the utility will not have to get those tokens.

## Command line parsing

This is done with the usual Python argument parser. Options supported are those from Dennis Box's summary of jobsub options actually used in the last 6 months. [list](https://cdcvs.fnal.gov/redmine/issues/23558) (Sorry, Fermilab folks only)

##  Tarball uploads

This is currently implemented using Python's `requests` module for https access to the [pubapi](https://indico.cern.ch/event/773049/contributions/3473381/attachments/1935973/3208194/CHEP19_Talk_Userpub.pdf) ; it is planned to improve it using the [streaming mulipart uploader](https://toolbelt.readthedocs.io/en/latest/uploading-data.html#streaming-multipart-data-encoder) so we do not have to read the whole tarball into memory.

## Tempates of .cmd .sh, and .dag files

The [Jinja](http://jinja.pocoo.org/docs/dev/templates/) template code is used to generate the job submission files.  For example, the template for the .cmd file for a simple submission is [simple.cmd](https://github.com/marcmengel/jobsub_lite/blob/master/templates/simple/simple.cmd) where a name (or expression) in doubled curly braces `{{name}}` is replaced when generating the output, and conditional geneartion is done with `{%if expr%}...{%endif%}`.  (There are other Jinja features, but that is mainly what is used now in jobsub_lite).  The majority of template replacement values are directly command line options or their defaults, which makes adding new features easy; you add an option (say `--fred` ) to the command line parser, and then add a suitable entry to the appropriate template(s) using that value ( `{{fred}}` or `{%if fred %} xyzzy={{fred}} {%endif%}` .
