package main

import (
	"log"
	"os"
	"os/exec"

	"github.com/clok/kemba"

	"github.com/hepcloud/jobsub/pkg/env"
)

const (
	DEFAULT_JOBSUB_PATH = "/opt/jobsub_lite"
	DEFAULT_PYTHON      = "/usr/bin/python3"
)

func main() {
	k := kemba.New("jobsub:submit")

	jobsubPath := env.Default("JOBSUB_PATH", DEFAULT_JOBSUB_PATH)
	k.Printf("jobsub path: %s", jobsubPath)

	python := env.Default("JOBSUB_PYTHON", DEFAULT_PYTHON)
	k.Printf("python: %s", python)

	jobsubSubmit := jobsubPath + "/lib/jobsub_submit.py"

	args := append([]string{jobsubSubmit}, os.Args[1:]...)
	cmd := exec.Command(python, args...)
	// users can have all kinds of stuff in their environment, especially
	// related to python, but also arbitrary stuff they can pass through to the
	// job. We need to remove/set vars that can affect the execution
	// environment for jobsub_submit.
	cmd.Env = env.Sanitized(
		env.StringFilter("LD_LIBRARY_PATH"),
		env.PrefixFilter("PYTHON"),
	)
	cmd.Env = append(cmd.Env,
		"PATH=/bin:/usr/bin:/usr/sbin:/usr/local/bin:"+jobsubPath+"/bin",
		"PYTHONPATH="+jobsubPath+"/lib",
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	k.Printf("running %v", cmd.Args)

	err := cmd.Run()
	if err != nil {
		log.Fatal(err)
	}
}
