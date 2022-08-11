#!/bin/bash

#
# decode_token utility
#
# Note that this does *not* check signatures...
#

decode_token() {
    #
    # token is 3 base64 segments separated by dots
    # we want the middle one.
    # the ending of the base64 segment is sometimes
    # chopped, so ignore errors about that
    #
    sed -e 's/.*\.\(.*\)\..*/\1==/' "$1" 2>/dev/null | base64 -d  2>/dev/null
}

get_field() {
    #
    # filter out a field from a json block
    # rip off up to "fieldname":, then rip off everything
    # after the comma.
    #
    # BUGS
    #    Borked for fields that contain commas.
    #
    sed -e "s/.*\"$1\"://" -e s'/,.*//'
}

usage() {
    echo "usage:"
    echo "    $0 [-e fieldname] tokenfile"
    echo "decodes SciToken file tokenfile"
    echo "option -e lets you extract a particular field"
}

case x$1 in
x-e) extractfilt="get_field $2"; shift; shift;;
x-h) usage; exit 0;;
x)   usage; exit 1;;
*)   extractfilt="cat";;
esac

decode_token $1 | $extractfilt
