Name:		jobsub_lite
Version:	beta10
Release:	1%{?dist}
Summary:	Job submission wrapper scripts

Group:		Fermi SCS Group
License:	Apache
URL:		https://github.com/marcmengel/jobsub_lite
Source0:	https://github.com/marcmengel/jobsub_lite/archive/refs/tags/%{version}.tar.gz

BuildRequires:	python3
Requires: python3
Requires: cigetcert
Requires: htgettoken
Requires: python36-jinja2
Requires: python3-condor
Requires: condor
Requires: condor-classads
Requires: condor-credmon-vault
Requires: python3-condor

%description
Job submission wrapper scripts


%prep
%setup
%global __python %{__python3} # Compile package using python3

%build
/bin/true

%install
mkdir -p $RPM_BUILD_ROOT/opt/jobsub_lite/bin
mkdir -p $RPM_BUILD_ROOT/opt/jobsub_lite/lib
mkdir -p $RPM_BUILD_ROOT/opt/jobsub_lite/templates
mkdir -p $RPM_BUILD_ROOT/etc/condor/config.d
mkdir -p $RPM_BUILD_ROOT/etc/profile.d
install -m 755 bin/* $RPM_BUILD_ROOT/opt/jobsub_lite/bin
install -m 755 lib/*.py $RPM_BUILD_ROOT/opt/jobsub_lite/lib/
for d in templates/*
do
    mkdir $RPM_BUILD_ROOT/opt/jobsub_lite/$d
    install -m 644 $d/* $RPM_BUILD_ROOT/opt/jobsub_lite/$d/
done
install -m 644 config.d/50-jobsub_lite.configs config.d/51-group_fermilab.configs $RPM_BUILD_ROOT/etc/condor/config.d/
install -m 755 spec/jobsub_lite.*h $RPM_BUILD_ROOT/etc/profile.d/

%files
%doc
%exclude /opt/jobsub_lite/*/*.py?
/opt/jobsub_lite/bin/condor_q
/opt/jobsub_lite/bin/condor_release
/opt/jobsub_lite/bin/condor_rm
/opt/jobsub_lite/bin/condor_submit
/opt/jobsub_lite/bin/condor_submit_dag
/opt/jobsub_lite/bin/condor_transfer_data
/opt/jobsub_lite/bin/condor_wait
/opt/jobsub_lite/bin/decode_token.sh
/opt/jobsub_lite/bin/fake_ifdh
/opt/jobsub_lite/bin/jobsub_cmd
/opt/jobsub_lite/bin/jobsub_hold
/opt/jobsub_lite/bin/jobsub_q
/opt/jobsub_lite/bin/jobsub_release
/opt/jobsub_lite/bin/jobsub_rm
/opt/jobsub_lite/bin/jobsub_submit
/opt/jobsub_lite/bin/jobsub_transfer_data
/opt/jobsub_lite/bin/jobsub_wait
/opt/jobsub_lite/lib/condor.py
/opt/jobsub_lite/lib/creds.py
/opt/jobsub_lite/lib/dagnabbit.py
/opt/jobsub_lite/lib/get_parser.py
/opt/jobsub_lite/lib/packages.py
/opt/jobsub_lite/lib/poms_wrap.py
/opt/jobsub_lite/lib/tarfiles.py
/opt/jobsub_lite/lib/utils.py
/opt/jobsub_lite/templates/dag/dag.dag.condor.sub
/opt/jobsub_lite/templates/dag/dagman_wrapper.sh
/opt/jobsub_lite/templates/dag/dagmax.config
/opt/jobsub_lite/templates/dataset_dag/dagbegin.cmd
/opt/jobsub_lite/templates/dataset_dag/dagend.cmd
/opt/jobsub_lite/templates/dataset_dag/dagman_wrapper.sh
/opt/jobsub_lite/templates/dataset_dag/dagmax.config
/opt/jobsub_lite/templates/dataset_dag/dataset.dag
/opt/jobsub_lite/templates/dataset_dag/dataset.dag.condor.sub
/opt/jobsub_lite/templates/dataset_dag/sambegin.sh
/opt/jobsub_lite/templates/dataset_dag/samend.sh
/opt/jobsub_lite/templates/maxconcurrent_dag/dagmax.config
/opt/jobsub_lite/templates/maxconcurrent_dag/maxconcurrent.dag
/opt/jobsub_lite/templates/simple/simple.cmd
/opt/jobsub_lite/templates/simple/simple.sh
%config(noreplace) /etc/condor/config.d/50-jobsub_lite.configs 
%config(noreplace) /etc/condor/config.d/51-group_fermilab.configs
/etc/profile.d/jobsub_lite.sh
/etc/profile.d/jobsub_lite.csh

%clean
rm -rf $RPM_BUILD_ROOT

%changelog
* Thu Jun 02 2022 Shreyas Bhat <sbhat@fnal.gov> beta10
- Marked /etc/condor files as %config(noreplace)

* Wed Feb 23 2022 Shreyas Bhat <sbhat@fnal.gov> beta8
- Added creation of /etc/profile.d in install section
- Only install .py files from lib/ and exclude all auto-compiled .py{co} files from lib/ in files section
- Remove __pycache__ files from files section

