from use_cases.videos.get_authenticated_user_videos import get_authenticated_user_videos_use_case


def test_partial_binded_kwargs_are_the_expected_ones():
    actual_keys = list(get_authenticated_user_videos_use_case.keywords.keys())
    expected_keys = [
        'search_in_database_fn',
        'describe_unprocessed_videos_in_database_fn',
        'describe_videos_in_database_fn'
    ]
    assert actual_keys == expected_keys
