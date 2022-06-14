package main

import (
	"log"
	"os"

	"github.com/urfave/cli/v2"

	"github.com/hepcloud/jobsub/pkg/jobsub"
)

func main() {
	app := &cli.App{
		Usage:     "release held job(s)",
		UsageText: "[options] JOBID",
		Flags:     jobsub.GlobalFlags,
		Action:    jobsub.CondorWrapper("release"),
	}

	err := app.Run(os.Args)
	if err != nil {
		log.Fatal(err)
	}
}
