package lit_test

import (
	"time"

	lit "github.com/lightning-ai/sdk/go"
)

func snippetUser() error {
	u, err := lit.GetUser("alice")
	if err != nil {
		return err
	}
	teamspaces, err := u.Teamspaces()
	if err != nil {
		return err
	}
	_ = teamspaces
	return nil
}

func snippetOrganization() error {
	o, err := lit.GetOrganization("acme")
	if err != nil {
		return err
	}
	teamspaces, err := o.Teamspaces()
	if err != nil {
		return err
	}
	_ = teamspaces
	return nil
}

func snippetTeamspace(u *lit.User) error {
	ts, err := lit.GetTeamspace("research", lit.TeamspaceOptions{Owner: u})
	if err != nil {
		return err
	}
	studios, err := ts.Studios()
	if err != nil {
		return err
	}
	_ = studios
	return nil
}

func snippetResearchTeamspace() (*lit.Teamspace, error) {
	u, err := lit.GetUser("alice")
	if err != nil {
		return nil, err
	}
	return lit.GetTeamspace("research", lit.TeamspaceOptions{Owner: u})
}

func snippetStudio() error {
	ts, err := snippetResearchTeamspace()
	if err != nil {
		return err
	}
	s, err := lit.CreateStudio("dev", lit.StudioOptions{
		Teamspace: ts,
		Machine:   lit.MachineL4,
	})
	if err != nil {
		return err
	}
	return lit.StartStudio(s, lit.StartStudioOptions{Machine: lit.MachineL4})
}

func snippetJob() error {
	ts, err := snippetResearchTeamspace()
	if err != nil {
		return err
	}
	j, err := lit.RunJob("train", lit.MachineL4, "python train.py", lit.JobOptions{
		Teamspace: ts,
		Image:     "pytorch/pytorch:latest",
	})
	if err != nil {
		return err
	}
	return j.Wait(lit.JobWaitOptions{Timeout: time.Hour})
}

func snippetMMT() error {
	ts, err := snippetResearchTeamspace()
	if err != nil {
		return err
	}
	m, err := lit.RunMMT("dist-train", 4, lit.MachineL4, "torchrun train.py", lit.MMTOptions{
		Teamspace: ts,
		Image:     "pytorch/pytorch:latest",
	})
	if err != nil {
		return err
	}
	machines, err := m.Machines()
	if err != nil {
		return err
	}
	_ = machines
	return nil
}

func snippetExistingStudioByName() error {
	ts, err := snippetResearchTeamspace()
	if err != nil {
		return err
	}
	s, err := lit.GetStudio("dev", lit.StudioOptions{
		Teamspace: ts,
	})
	if err != nil {
		return err
	}
	return s.Stop()
}

func snippetExistingStudioByID() error {
	ts, err := lit.GetTeamspace("", lit.TeamspaceOptions{ID: "teamspace-id"})
	if err != nil {
		return err
	}
	s, err := lit.GetStudio("", lit.StudioOptions{
		ID:        "studio-id",
		Teamspace: ts,
	})
	if err != nil {
		return err
	}
	_ = s
	return nil
}

func snippetExistingJobByName() error {
	ts, err := snippetResearchTeamspace()
	if err != nil {
		return err
	}
	j, err := lit.GetJob("train", lit.JobOptions{
		Teamspace: ts,
	})
	if err != nil {
		return err
	}
	logs, err := j.Logs()
	if err != nil {
		return err
	}
	_ = logs
	return nil
}

func snippetExistingJobByID() error {
	ts, err := lit.GetTeamspace("", lit.TeamspaceOptions{ID: "teamspace-id"})
	if err != nil {
		return err
	}
	j, err := lit.GetJob("", lit.JobOptions{
		ID:        "job-id",
		Teamspace: ts,
	})
	if err != nil {
		return err
	}
	_ = j
	return nil
}

func snippetExistingMMTByName() error {
	ts, err := snippetResearchTeamspace()
	if err != nil {
		return err
	}
	m, err := lit.GetMMT("dist-train", lit.MMTOptions{
		Teamspace: ts,
	})
	if err != nil {
		return err
	}
	machines, err := m.Machines()
	if err != nil {
		return err
	}
	_ = machines
	return nil
}

func snippetExistingMMTByID() error {
	ts, err := lit.GetTeamspace("", lit.TeamspaceOptions{ID: "teamspace-id"})
	if err != nil {
		return err
	}
	m, err := lit.GetMMT("", lit.MMTOptions{
		ID:        "mmt-id",
		Teamspace: ts,
	})
	if err != nil {
		return err
	}
	_ = m
	return nil
}
