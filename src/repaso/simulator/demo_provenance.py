from repaso.tools.cassette_provenance import CassetteProvenance

NO_PROVENANCE = (
    "This cassette carries no provenance record beside it: nothing here says which models\n"
    "wrote these answers, when, or what the recording cost."
)
CLEAN_TREE = "at commit"
MODIFIED_TREE = "on top of commit"


def replay_note(provenance: CassetteProvenance | None) -> str:
    if provenance is None:
        return NO_PROVENANCE
    at = MODIFIED_TREE if provenance.working_tree_modified else CLEAN_TREE
    return "\n".join(
        (
            f"The model outputs are replayed from a recording made on "
            f"{provenance.recorded_at.date().isoformat()} in {provenance.region}, against "
            f"{len(provenance.model_ids)} model ids,",
            f"{at} {provenance.commit[:12]}: the tokens and dollars above are what that one "
            f"recording measured.",
            "This replay reached no network and spent nothing, and it is not evidence that "
            "the models",
            "would answer this way again.",
        )
    )
