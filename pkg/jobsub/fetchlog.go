package jobsub

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/clok/kemba"
	"github.com/urfave/cli/v2"
)

var FetchlogFlags = []cli.Flag{
	&cli.StringFlag{
		Name:     "jobid",
		Aliases:  []string{"J", "job"},
		Usage:    "job/submission ID",
		Required: true,
	},
	&cli.StringFlag{
		Name:    "destdir",
		Aliases: []string{"dest-dir", "unzipdir"},
		Usage:   "Directory to automatically unarchive logs into",
	},
	&cli.StringFlag{
		Name:  "archive-format",
		Usage: "format for downloaded archive:\"tar\" (default,compressed) or \"zip\"",
		Value: "tar",
	},
}

func Fetchlog(ctx *cli.Context) error {
	k := kemba.New("jobsub:fetchlog")

	// get creds
	if err := CheckCreds(ctx); err != nil {
		return err
	}

	// decompose job ID so we can build the condor command
	j := Job{ID: ctx.String("jobid")}
	if err := j.DecomposeID(); err != nil {
		return fmt.Errorf("error decomposing job id: %w", err)
	}

	// determine where condor_transfer_data will put output
	iwd, err := j.GetAttribute("SUBMIT_Iwd")
	if err != nil {
		return fmt.Errorf("error determining log location: %w", err)
	}
	k.Printf("sandbox directory: %s", iwd)

	// make sure output directory exists
	if _, err := os.Stat(iwd); os.IsNotExist(err) {
		k.Println("sandbox directory doesn't exists, try to make it")
		if err := os.Mkdir(iwd, 0750); err != nil {
			return fmt.Errorf("sandbox directory %s doesn't exist and can't be created: %w", iwd, err)
		}
	} else if err != nil {
		k.Printf("Stat(iwd) got error, will try anyways: %s", err.Error())
	}

	// run condor_transfer_data to get output from schedd
	cmd := exec.Command("condor_transfer_data")
	cmd.Args = append(cmd.Args, "-name", j.Schedd)
	if j.Cluster {
		cmd.Args = append(cmd.Args, j.Seq)
	} else {
		cmd.Args = append(cmd.Args, j.Seq+"."+j.Proc)
	}
	k.Printf("running %v", cmd.Args)
	cmd.Stderr = os.Stderr
	cmd.Stdout = os.Stdout
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("error fetching output: %w", err)
	}

	// if user wants output in a specific directory, just rename it
	if destdir := ctx.String("destdir"); destdir != "" {
		k.Printf("moving sandbox directory to %s", destdir)
		err := os.Rename(iwd, destdir)
		if err != nil {
			return fmt.Errorf("error moving sandbox directory: %w", err)
		}
		return nil
	}

	// build tarball
	// could use archive/tar etc but running a command is simpler for current use case
	files, err := os.ReadDir(iwd)
	if err != nil {
		return fmt.Errorf("error reading sandbox: %w", err)
	}
	k.Println(files)
	switch af := ctx.String("archive-format"); af {
	case "zip":
		cmd = exec.Command("zip", "-j", j.String()+".zip")
		// -j: junk (don't record) directory names
		for _, f := range files {
			cmd.Args = append(cmd.Args, iwd+"/"+f.Name())
		}
	case "tar":
		cmd = exec.Command("tar", "-C", iwd, "-czf", j.String()+".tgz")
		// -C: move into directory so paths are relative
		// -c: create
		// -z: gzip
		// -f: filename
		for _, f := range files {
			cmd.Args = append(cmd.Args, f.Name())
		}
	default:
		return fmt.Errorf("unrecognized archive format %s", af)
	}
	k.Printf("running %v", cmd.Args)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("error writing archive: %w", err)
	}

	return nil
}
