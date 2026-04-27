class StatsServiceError(Exception):
    pass

class TeamNotFoundError(StatsServiceError):
    pass

class InvalidResponseError(StatsServiceError):
    pass

class RequestFailedError(StatsServiceError):
    pass