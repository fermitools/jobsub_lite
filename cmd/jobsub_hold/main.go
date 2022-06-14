package main

import (
	"log"
	"os"

	"github.com/urfave/cli/v2"

	"github.com/hepcloud/jobsub/pkg/jobsub"
)

func main() {
	app := &cli.App{
		Usage:     "hold job(s)",
		UsageText: "[options] JOBID",
		Flags:     jobsub.GlobalFlags,
		Action:    jobsub.CondorWrapper("hold"),
	}

	err := app.Run(os.Args)
	if err != nil {
		log.Fatal(err)
	}
}
