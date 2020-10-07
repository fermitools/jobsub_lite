#!/bin/sh

common="--devserver --group fermilab --resource-provides=usage_model=OPPORTUNISTIC,DEDICATED"
#try assorted permutations of tarfile uploads
for dbtype in cvmfs pnfs
do
    for tft in "--tar_file_name dropbox:`pwd`/prestuff.tgz"  "--tar_file_name tardir:`pwd`/stuff"
    do
         jobsub_submit $common --use-$dbtype-dropbox $tft file://`pwd`/checktar.sh
    done
done

tft="--tar_file_name /pnfs/nova/scratch/users/mengel/prestuff.tgz"
jobsub_submit $common $tft file://`pwd`/checktar.sh
