cmake_minimum_required(VERSION 3.20)
project(trading_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(broker_sim
    src/broker/BrokerSimulator.cpp
    src/journal/EventJournal.cpp
    src/order/OrderGateway.cpp
    src/position/PositionKeeper.cpp
    src/risk/RiskChecker.cpp
)
target_include_directories(broker_sim PUBLIC include src)

enable_testing()
add_subdirectory(tests)
