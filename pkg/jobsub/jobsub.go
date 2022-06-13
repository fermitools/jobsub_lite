package jobsub

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/clok/kemba"
	"github.com/urfave/cli/v2"
)

var GlobalFlags = []cli.Flag{
	&cli.StringFlag{
		Name:    "group",
		Aliases: []string{"G"},
		Usage:   "experiment/vo override",
	},
	&cli.BoolFlag{
		Name:  "token",
		Usage: "use SciToken for auth",
		Value: true,
	},
	&cli.BoolFlag{
		Name:  "proxy",
		Usage: "use X509 proxy for auth",
		Value: false,
	},
}

func CheckCreds(ctx *cli.Context) error {
	k := kemba.New("jobsub:CheckCreds")
	group := ctx.String("group")
	if group == "" {
		var err error
		group, err = GetExp()
		if err != nil {
			return fmt.Errorf("error determining experiment: %w", err)
		}
	}
	k.Printf("got group: %s", group)

	role, err := GetRole()
	if err != nil {
		return fmt.Errorf("error determining role: %w", err)
	}
	k.Printf("got role: %s", role)

	if ctx.Bool("token") {
		k.Log("getting token")
		if err := GetToken(group, role); err != nil {
			return err
		}
	}
	if ctx.Bool("proxy") {
		k.Log("getting proxy")
		if err := GetProxy(group, role); err != nil {
			return err
		}
	}

	return nil
}

func CondorWrapper(command string) func(ctx *cli.Context) error {
	k := kemba.New("jobsub:" + command)
	return func(ctx *cli.Context) error {
		if ctx.NArg() < 1 {
			return fmt.Errorf("must specify at least one job")
		}
		jobs := make([]Job, 0)
		args := make([]string, ctx.Args().Len())
		for _, jid := range ctx.Args().Slice() {
			j := Job{ID: jid}
			if err := j.DecomposeID(); err == nil {
				jobs = append(jobs, j)
			} else {
				// not a job id, must be an argument to pass through?
				args = append(args, jid)
			}
		}

		// get creds
		if err := CheckCreds(ctx); err != nil {
			return err
		}

		// run the command for each job
		for _, j := range jobs {
			jargs := append(args, "-name", j.Schedd)
			if j.Cluster {
				jargs = append(jargs, j.Seq)
			} else {
				jargs = append(jargs, j.Seq+"."+j.Proc)
			}
			condor_command := "condor_" + command
			k.Printf("running %s with args %v", condor_command, jargs)
			cmd := exec.Command(condor_command, jargs...)
			cmd.Stderr = os.Stderr
			cmd.Stdout = os.Stdout
			if err := cmd.Run(); err != nil {
				return fmt.Errorf("error running condor command: %w", err)
			}
		}
		return nil
	}
}
