include(FetchContent)
FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.9.1
)
FetchContent_MakeAvailable(Catch2)

add_executable(test_broker_simulator test_broker_simulator.cpp)
target_link_libraries(test_broker_simulator PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_order_gateway test_order_gateway.cpp)
target_link_libraries(test_order_gateway PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_position_keeper test_position_keeper.cpp)
target_link_libraries(test_position_keeper PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_risk_checker test_risk_checker.cpp)
target_link_libraries(test_risk_checker PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_market_data_handler test_market_data_handler.cpp)
target_link_libraries(test_market_data_handler PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_alpaca_gateway test_alpaca_gateway.cpp)
target_link_libraries(test_alpaca_gateway PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_execution_scheduler test_execution_scheduler.cpp)
target_link_libraries(test_execution_scheduler PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_kill_switch test_kill_switch.cpp)
target_link_libraries(test_kill_switch PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_compliance_checker test_compliance_checker.cpp)
target_link_libraries(test_compliance_checker PRIVATE broker_sim Catch2::Catch2WithMain)

add_executable(test_reconciliation test_reconciliation.cpp)
target_link_libraries(test_reconciliation PRIVATE broker_sim Catch2::Catch2WithMain)

list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(CTest)
include(Catch)
catch_discover_tests(test_broker_simulator)
catch_discover_tests(test_order_gateway)
catch_discover_tests(test_position_keeper)
catch_discover_tests(test_risk_checker)
catch_discover_tests(test_market_data_handler)
catch_discover_tests(test_alpaca_gateway)
catch_discover_tests(test_execution_scheduler)
catch_discover_tests(test_kill_switch)
catch_discover_tests(test_compliance_checker)
catch_discover_tests(test_reconciliation)
