package lit

// Owner is implemented by resources that can own teamspaces.
type Owner interface {
	// ID returns the owner ID.
	ID() string
	// Name returns the owner name.
	Name() string
	// CreateTeamspace creates a teamspace owned by this owner.
	CreateTeamspace(name string) (*Teamspace, error)
	// Teamspaces lists teamspaces owned by this owner.
	Teamspaces() ([]*Teamspace, error)
}

var (
	_ Owner = (*User)(nil)
	_ Owner = (*Organization)(nil)
)

func sameOwner(left, right Owner) bool {
	if left == nil || right == nil {
		return left == right
	}
	return left.ID() == right.ID() && left.Name() == right.Name()
}
