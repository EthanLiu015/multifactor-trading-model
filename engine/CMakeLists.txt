cmake_minimum_required(VERSION 3.20)
project(trading_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

set(USE_TLS ON CACHE BOOL "" FORCE)  # macOS auto-selects Apple SecureTransport, no OpenSSL needed
FetchContent_Declare(
    ixwebsocket
    GIT_REPOSITORY https://github.com/machinezone/IXWebSocket.git
    GIT_TAG v12.0.1
)
FetchContent_MakeAvailable(ixwebsocket)

FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.12.0
)
FetchContent_MakeAvailable(nlohmann_json)

find_package(CURL REQUIRED)  # system libcurl -- REST client for AlpacaGateway, no FetchContent needed

add_library(broker_sim
    src/broker/BrokerSimulator.cpp
    src/broker/AlpacaGateway.cpp
    src/journal/EventJournal.cpp
    src/order/OrderGateway.cpp
    src/position/PositionKeeper.cpp
    src/risk/RiskChecker.cpp
    src/marketdata/MarketDataHandler.cpp
    src/marketdata/AlpacaMarketDataStream.cpp
    src/execution/ExecutionScheduler.cpp
)
target_include_directories(broker_sim PUBLIC include src)
target_link_libraries(broker_sim PRIVATE nlohmann_json::nlohmann_json CURL::libcurl)
# PUBLIC: AlpacaMarketDataStream.hpp and AlpacaGateway.hpp (public headers)
# hold an ix::WebSocket member by value, so anything including them needs
# ixwebsocket's headers too.
target_link_libraries(broker_sim PUBLIC ixwebsocket::ixwebsocket)

add_executable(smoke_market_data tools/smoke_market_data.cpp)
target_link_libraries(smoke_market_data PRIVATE broker_sim)

add_executable(smoke_alpaca_gateway tools/smoke_alpaca_gateway.cpp)
target_link_libraries(smoke_alpaca_gateway PRIVATE broker_sim)

enable_testing()
add_subdirectory(tests)
