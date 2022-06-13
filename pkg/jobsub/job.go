package jobsub

import (
	"fmt"
	"regexp"

	"github.com/clok/kemba"
	"github.com/retzkek/htcondor-go"
)

var jobIDRegexp *regexp.Regexp

func init() {
	jobIDRegexp = regexp.MustCompile("(\\d+)(?:\\.(\\d+))?@([\\w\\.]+)")
}

// Job is a single HTCondor batch job or cluster
type Job struct {
	ID      string
	Seq     string
	Proc    string
	Schedd  string
	Cluster bool
}

// DecomposeID breaks out the job's ID into components.
func (j *Job) DecomposeID() error {
	if matches := jobIDRegexp.FindStringSubmatch(j.ID); len(matches) == 4 {
		j.Seq = matches[1]
		j.Proc = matches[2]
		j.Schedd = matches[3]
	} else {
		return fmt.Errorf("error parsing job ID %s", j.ID)
	}
	if j.Proc == "" {
		j.Proc = "0"
		j.Cluster = true
	}
	return nil
}

// ComposeID builds the canonical job ID out of components.
func (j *Job) ComposeID() string {
	if j.Seq == "" {
		// well it looks like the ID was never decomposed (or components set). Maybe ID is right.
		return j.ID
	}
	if j.Cluster {
		return fmt.Sprintf("%s@%s", j.Seq, j.Schedd)
	}
	return fmt.Sprintf("%s.%s@%s", j.Seq, j.Proc, j.Schedd)
}

// String returns a string representation of the job (job ID)
func (j *Job) String() string {
	if j.ID != "" {
		return j.ID
	}
	return j.ComposeID()
}

// GetAttribute uses condor_q to get the specified attribute for the job. It is
// an error if the attribute is not found.
func (j *Job) GetAttribute(attr string) (string, error) {
	k := kemba.New("jobsub:Job:GetAttribute")
	ccmd := htcondor.NewCommand("condor_q").WithName(j.Schedd).WithArg(j.Seq).WithAttribute(attr)
	k.Printf("running %s with args %v", ccmd.Command, ccmd.MakeArgs())
	ads, err := ccmd.Run()
	if err != nil {
		return "", err
	}
	if len(ads) < 1 {
		return "", fmt.Errorf("job %s not found on schedd %s", j.Seq, j.Schedd)
	}
	k.Println(ads)
	val, found := ads[0][attr]
	if !found {
		return "", fmt.Errorf("attribute %s not found for job", attr)
	}
	return val.String(), nil
}
