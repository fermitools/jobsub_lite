package main

import (
	"log"
	"os"

	"github.com/urfave/cli/v2"

	"github.com/hepcloud/jobsub/pkg/jobsub"
)

func main() {
	flags := append(jobsub.GlobalFlags, jobsub.FetchlogFlags...)
	app := &cli.App{
		Usage:     "fetch job logs",
		UsageText: "[options]",
		Flags:     flags,
		Action:    jobsub.Fetchlog,
	}

	err := app.Run(os.Args)
	if err != nil {
		log.Fatal(err)
	}
}
