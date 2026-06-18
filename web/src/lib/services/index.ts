/**
 * Services barrel export — single import point for all API service modules.
 *
 * Usage:
 *   import { userService, tokenService, channelService } from '@/lib/services';
 *
 * Each service is a namespace of typed functions that return AxiosResponse<T>.
 */
export { login, register, logout, getSelf, getUsers, updateUser, deleteUser, manageUser, searchUsers } from './user';
export type {
  UserInfo,
  LoginRequest,
  RegisterRequest,
  PaginatedResponse as UserPaginatedResponse,
  ApiResult as UserApiResult,
} from './user';

export { getTokens, getToken, createToken, updateToken, deleteToken, getAvailableModels } from './token';
export type { Token, CreateTokenRequest, UpdateTokenRequest, PaginatedTokenResponse } from './token';

export { getChannels, getChannel, createChannel, updateChannel, deleteChannel, testChannel, manageChannel, searchChannels } from './channel';
export type { Channel, PaginatedChannelResponse } from './channel';

export { getLogs, searchLogs, deleteLogs } from './log';
export type { LogEntry, LogSearchParams, PaginatedLogResponse } from './log';

export { getOptions, updateOption, getOptionByKey } from './setting';
export type { OptionItem } from './setting';

export { getRechargeRequests, createRechargeRequest, reviewRecharge } from './recharge';
export type { TopUpRequest, CreateRechargeRequest, PaginatedRechargeResponse } from './recharge';
