package jobsub

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/clok/kemba"
	"github.com/urfave/cli/v2"
)

func Queue(ctx *cli.Context) error {
	k := kemba.New("jobsub:queue")

	// get creds
	if err := CheckCreds(ctx); err != nil {
		return err
	}

	group := ctx.String("group")
	if group == "" {
		var err error
		group, err = GetExp()
		if err != nil {
			return fmt.Errorf("error determining experiment: %w", err)
		}
	}

	constraint := fmt.Sprintf("Jobsub_Group==\"%s\"", group)

	args := []string{"-global", "-constraint", constraint}

	jobs := make([]Job, 0)
	if ctx.NArg() > 0 {
		for _, jid := range ctx.Args().Slice() {
			j := Job{ID: jid}
			if err := j.DecomposeID(); err == nil {
				jobs = append(jobs, j)
			} else {
				// not a job id, must be an argument to pass through?
				args = append(args, jid)
			}
		}
	}
	if len(jobs) > 0 {
		for _, j := range jobs {
			if j.Cluster {
				args = append(args, j.Seq)
			} else {
				args = append(args, j.Seq+"."+j.Proc)
			}
		}
	} else {
		// TODO only get user's jobs
	}

	condor_command := "condor_q"
	k.Printf("running %s with args %v", condor_command, args)
	cmd := exec.Command(condor_command, args...)
	cmd.Stderr = os.Stderr
	cmd.Stdout = os.Stdout
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("error running condor command: %w", err)
	}
	return nil
}
