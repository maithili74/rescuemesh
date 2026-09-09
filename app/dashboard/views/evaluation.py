import streamlit as st

from app.dashboard.services.metrics import (
    get_evaluation_metrics,
    get_latest_test_results,
    get_rescue_evaluation_rows,
    get_scenario_benchmark_results,
)


def percentage(
    value,
):
    if value is None:
        return "—"

    return (
        f"{value * 100:.1f}%"
    )


def render_evaluation_view():

    st.header(
        "Impact & Evaluation"
    )

    st.caption(
        "Measured RescueMesh outcomes from the real "
        "rescue database and automated test suite."
    )

    st.info(
        "These values are calculated from actual "
        "RescueMesh operations. Performance numbers "
        "are not hard-coded."
    )

    metrics = (
        get_evaluation_metrics()
    )

    # =====================================================
    # IMPACT
    # =====================================================

    st.subheader(
        "Food Rescue Impact"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Confirmed Food Rescued",
            (
                f"{metrics['confirmed_lbs']:.0f} lbs"
            ),
        )

    with col2:

        st.metric(
            "Confirmed Rescue Rate",
            percentage(
                metrics[
                    "confirmed_rescue_rate"
                ]
            ),
        )

    with col3:

        st.metric(
            "Completed Rescues",
            metrics[
                "completed_operations"
            ],
        )

    with col4:

        st.metric(
            "Operation Completion Rate",
            percentage(
                metrics[
                    "completion_rate"
                ]
            ),
        )

    st.caption(
        "Confirmed food is counted only after the "
        "receiving pantry confirms that the food "
        "physically arrived."
    )

    st.divider()

    # =====================================================
    # LOGISTICS
    # =====================================================

    st.subheader(
        "Logistics Performance"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Avg Drivers / Rescue",
            (
                f"{metrics['average_drivers_per_rescue']:.2f}"
            ),
        )

    with col2:

        st.metric(
            "Avg Stops / Rescue",
            (
                f"{metrics['average_stops_per_rescue']:.2f}"
            ),
        )

    with col3:

        st.metric(
            "Avg Route Distance",
            (
                f"{metrics['average_route_distance_miles']:.1f} mi"
            ),
        )

    with col4:

        st.metric(
            "Unrescued Food",
            (
                f"{metrics['unrescued_lbs']:.0f} lbs"
            ),
        )

    st.divider()

    # =====================================================
    # RESILIENCE
    # =====================================================

    st.subheader(
        "Autonomy & Recovery"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Disrupted Rescues",
            metrics[
                "disrupted_operations"
            ],
        )

    with col2:

        st.metric(
            "Human Escalations",
            metrics[
                "total_escalations"
            ],
        )

    with col3:

        st.metric(
            "Autonomous Recovery Rate",
            percentage(
                metrics[
                    "autonomous_recovery_rate"
                ]
            ),
        )

    with col4:

        st.metric(
            "Human Escalation Rate",
            percentage(
                metrics[
                    "human_escalation_rate"
                ]
            ),
        )

    if (
        metrics[
            "disrupted_operations"
        ]
        ==
        0
    ):

        st.caption(
            "No disruption scenarios exist in the current "
            "demo database yet, so recovery metrics are "
            "not calculated."
        )

    else:

        st.caption(
            "Autonomous recovery counts disrupted rescues "
            "that ultimately completed without creating "
            "a human escalation."
        )

    st.divider()

    # =====================================================
    # CURRENT DATASET SUMMARY
    # =====================================================

    st.subheader(
        "Current Evaluation Set"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Rescue Operations",
            metrics[
                "total_operations"
            ],
        )

    with col2:

        st.metric(
            "Food Entering Operations",
            (
                f"{metrics['total_donation_lbs']:.0f} lbs"
            ),
        )

    with col3:

        st.metric(
            "Full Completions",
            metrics[
                "fully_completed_operations"
            ],
        )

    with col4:

        st.metric(
            "Partial Completions",
            metrics[
                "partially_completed_operations"
            ],
        )

    st.divider()

    # =====================================================
    # RESCUE-BY-RESCUE RESULTS
    # =====================================================

    st.subheader(
        "Rescue-by-Rescue Results"
    )

    rescue_rows = (
        get_rescue_evaluation_rows()
    )

    if rescue_rows:

        st.dataframe(
            rescue_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No rescue operations have been evaluated yet."
        )

    st.divider()

    # =====================================================
    # AUTOMATED TEST SUITE
    # =====================================================

    st.subheader(
        "Automated System Evaluation"
    )

    test_results = (
        get_latest_test_results()
    )

    if test_results is None:

        st.warning(
            "No recorded automated evaluation run yet."
        )

        st.code(
            "python scripts/run_evaluation.py",
            language="bash",
        )

    else:

        col1, col2, col3, col4 = (
            st.columns(4)
        )

        with col1:

            st.metric(
                "Tests Passed",
                test_results[
                    "passed"
                ],
            )

        with col2:

            st.metric(
                "Tests Failed",
                test_results[
                    "failed"
                ],
            )

        with col3:

            st.metric(
                "Test Pass Rate",
                percentage(
                    test_results[
                        "pass_rate"
                    ]
                ),
            )

        with col4:

            st.metric(
                "Test Duration",
                (
                    f"{test_results['duration_seconds']:.1f}s"
                ),
            )

        if (
            test_results[
                "failed"
            ]
            ==
            0
        ):

            st.success(
                "✅ All evaluated automated tests passed."
            )

        else:

            st.error(
                "Some automated tests failed. "
                "Review the test output before using "
                "these results in the demo."
            )

        st.caption(
            f"Latest evaluation run: "
            f"{test_results['timestamp']}"
        )
        
        
        
    # =========================================================
    # SCENARIO BENCHMARK
    # =========================================================

    st.divider()

    st.subheader(
        "Scenario Benchmark"
    )

    st.caption(
        "RescueMesh is also evaluated under specific "
        "logistics constraints and boundary conditions."
    )

    scenario_results = (
        get_scenario_benchmark_results()
    )

    if scenario_results is None:

        st.warning(
            "No scenario benchmark has been recorded yet."
        )

        st.code(
            "python scripts/run_scenario_benchmark.py",
            language="bash",
        )

    else:

        col1, col2, col3 = (
            st.columns(3)
        )

        with col1:

            st.metric(
                "Scenarios Evaluated",
                scenario_results[
                    "total_scenarios"
                ],
            )

        with col2:

            st.metric(
                "Scenarios Passed",
                scenario_results[
                    "passed"
                ],
            )

        with col3:

            st.metric(
                "Scenario Pass Rate",
                percentage(
                    scenario_results[
                        "pass_rate"
                    ]
                ),
            )

        if (
            scenario_results[
                "failed"
            ]
            ==
            0
        ):

            st.success(
                "✅ All evaluated scenarios behaved "
                "as expected."
            )

        else:

            st.error(
                f"{scenario_results['failed']} scenario(s) "
                "did not behave as expected."
            )

        scenario_rows = []

        for scenario in scenario_results[
            "scenarios"
        ]:

            scenario_rows.append(
                {
                    "Scenario":
                        scenario["name"],

                    "Condition":
                        scenario["description"],

                    "Expected Behavior":
                        scenario[
                            "expected_behavior"
                        ],

                    "Result":
                        (
                            "✅ Pass"
                            if scenario["passed"]
                            else "❌ Fail"
                        ),
                }
            )

        st.dataframe(
            scenario_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            f"Latest benchmark run: "
            f"{scenario_results['timestamp']}"
        )

    # =====================================================
    # DEFINITIONS
    # =====================================================

    with st.expander(
        "How are these metrics calculated?"
    ):

        st.markdown(
            """
**Confirmed Food Rescued**  
Food is counted only when a pantry confirms receipt.
A driver's delivery report alone does not count.

**Confirmed Rescue Rate**  
Confirmed pounds divided by the total pounds from
donations that entered RescueMesh operations.

**Operation Completion Rate**  
Completed or partially completed rescue operations
divided by total rescue operations.

**Autonomous Recovery Rate**  
Among disrupted rescues that ultimately completed,
the percentage that completed without requiring a
human escalation.

**Human Escalation Rate**  
The percentage of disrupted rescue operations that
required at least one human escalation.

**Average Drivers / Rescue**  
Average number of distinct drivers assigned to each
rescue operation.

**Average Route Distance**  
Average optimizer-generated route distance across
RescueMesh operations.
            """
        )
        
