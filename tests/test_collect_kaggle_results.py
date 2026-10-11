from collect_kaggle_results import classify, rank


def test_classify_requires_images_and_priors_for_complete():
    assert classify({"completed_images": 90, "failed_images": 0, "text_prior_completed": 45}) == "complete"
    assert (
        classify({"completed_images": 90, "failed_images": 0, "text_prior_completed": 20})
        == "image_complete_prior_partial"
    )
    assert classify({"completed_images": 42, "failed_images": 48}) == "image_partial"
    assert classify({"status": "vision_canary_failed"}) == "vision_canary_failed"


def test_complete_run_outranks_newer_failed_run():
    complete = {
        "classification": "complete",
        "completed_images": 90,
        "text_prior_completed": 45,
        "version": 5,
    }
    failed = {
        "classification": "vision_canary_failed",
        "completed_images": 0,
        "text_prior_completed": 0,
        "version": 9,
    }
    assert rank(complete) > rank(failed)
