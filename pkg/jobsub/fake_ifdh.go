package jobsub

import (
	"fmt"
	"os"
	"os/exec"
	"os/user"
	"strings"
	"time"

	"github.com/clok/kemba"
	"github.com/lestrrat-go/jwx/jwt"
)

const (
	DEFAULT_VAULT_HOST = "fermicloud543.fnal.gov"
	// DEFAULT_ROLE is the default role for htgettoken/vault, which we don't
	// want to ask for explicitely
	DEFAULT_ROLE = "Analysis"
)

// GetExp tries to determine the user's experiment/vo
func GetExp() (string, error) {
	// check if a recognized env var is set
	for _, ev := range []string{"GROUP", "EXPERIMENT", "SAM_EXPERIMENT"} {
		if g, found := os.LookupEnv(ev); found {
			return g, nil
		}
	}
	// use the primary group name
	u, err := user.Current()
	if err != nil {
		return "", fmt.Errorf("unable to determine experiment name from group: %w", err)
	}
	g, err := user.LookupGroupId(u.Gid)
	if err != nil {
		return "", fmt.Errorf("unable to determine experiment name from group: %w", err)
	}

	return g.Name, nil
}

// GetRole determines the user's role from the environment
func GetRole() (string, error) {
	u, err := user.Current()
	if err != nil {
		return "", fmt.Errorf("unable to determine current user: %w", err)
	}
	if strings.HasSuffix(u.Name, "pro") {
		return "Production", nil
	}
	return DEFAULT_ROLE, nil
}

// GetToken checks for a valid token, otherwise obtains one with htgettoken and
// sets BEARER_TOKEN_FILE
func GetToken(exp, role string) error {
	k := kemba.New("ifdh:GetToken")

	u, err := user.Current()
	if err != nil {
		return fmt.Errorf("unable to determine current user: %w", err)
	}

	issuer := exp
	if exp == "samdev" {
		issuer = "fermilab"
	}

	tokenfile := fmt.Sprintf("%s/bt_token_%s_%s_%s", os.TempDir(), issuer, role, u.Uid)
	k.Printf("tokenfile: %s", tokenfile)
	if err := os.Setenv("BEARER_TOKEN_FILE", tokenfile); err != nil {
		return fmt.Errorf("error setting BEARER_TOKEN_FILE: %w", err)
	}

	token, err := jwt.ReadFile(tokenfile)
	if err == nil {
		k.Log("token exists")
		if time.Now().Before(token.Expiration()) {
			k.Log("existing token is still valid")
			return nil
		}
	}

	k.Log("getting new token")
	cmd := exec.Command("htgettoken", "-a", DEFAULT_VAULT_HOST, "-i", issuer)
	// htgettoken won't actually give you a token with the default role if you
	// ask for it explicitely. Seems like a bug?
	if role != DEFAULT_ROLE {
		cmd.Args = append(cmd.Args, "-r", strings.ToLower(role))
	}
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("error running htgettoken: %w", err)
	}
	return nil
}

// GetProxy checks for a valid proxy, otherwise obtains one with voms-proxy-init
func GetProxy(exp, role string) error {
	k := kemba.New("ifdh:GetProxy")

	u, err := user.Current()
	if err != nil {
		return fmt.Errorf("unable to determine current user: %w", err)
	}

	issuer := exp
	if exp == "samdev" {
		issuer = "fermilab"
	}

	certfile := fmt.Sprintf("%s/x509up_u%s", os.TempDir(), u.Uid)
	k.Printf("certfile: %s", certfile)
	vomsfile := fmt.Sprintf("%s/x509up_%s_%s_%s", os.TempDir(), exp, role, u.Uid)
	k.Printf("vomsfile: %s", vomsfile)

	cmd := exec.Command("voms-proxy-info", "-exists", "-valid", "0:10", "-file", vomsfile)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	k.Printf("running %s with args %v", cmd.Path, cmd.Args)
	if cmd.Run() == nil {
		k.Log("proxy exists and is valid")
		return nil
	}
	cmd = exec.Command("cigetcert", "-i", "Fermi National Accelerator Laboratory", "-n", "-o", certfile)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	k.Printf("running %s with args %v", cmd.Path, cmd.Args)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("error running cigetcert: %w", err)
	}

	cmd = exec.Command("voms-proxy-init",
		"-dont-verify-ac",
		"-valid", "120:00",
		"-rfc",
		"-noregen",
		"-debug",
		"-cert", certfile,
		"-key", certfile,
		"-out", vomsfile,
		"-voms", fmt.Sprintf("%s:/%s/Role=%s", issuer, exp, role),
	)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	k.Printf("running %s with args %v", cmd.Path, cmd.Args)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("error running voms-proxy-init: %w", err)
	}

	return nil
}
