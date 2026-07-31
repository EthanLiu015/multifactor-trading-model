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

list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(CTest)
include(Catch)
catch_discover_tests(test_broker_simulator)
catch_discover_tests(test_order_gateway)
catch_discover_tests(test_position_keeper)
catch_discover_tests(test_risk_checker)
