// 登录方式总集合：
// - account: 账号密码
// - mobile: 手机/邮箱验证码
// - qrcode: App 扫码
// - wechat/dingtalk: 第三方扫码
export type LoginMethod = 'account' | 'mobile' | 'qrcode' | 'wechat' | 'dingtalk';

// 社交登录方式子集，专门用于图标上传和社交登录切换等场景。
export type SocialLoginMethod = Extract<LoginMethod, 'wechat' | 'dingtalk'>;

// 真实登录接口需要的最小凭证结构。
export interface LoginCredentials {
  username: string;
  password: string;
}

// 登录页对外暴露的唯一能力：执行登录（由上层注入具体实现）。
export interface LoginPageProps {
  // onLogin: (credentials: LoginCredentials) => Promise<void>;
  onIamLogin?: (code: string) => Promise<void>;
}

// 表单错误集合，key 对应字段名（如 email/password/general）。
export type LoginErrors = Record<string, string>;
