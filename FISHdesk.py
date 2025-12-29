import pygame
import numpy as np
import random
import sys
import os
from enum import Enum

try:
    import win32api
    import win32con
    import win32gui
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

# --- 全局配置参数 ---
NUM_POINTS = 10000  # 减少点数，章鱼形状不需要那么多点
TARGET_FPS = 30     # 降低帧率，使动画更平滑
DOT_SIZE = 1
TRANSPARENT_COLOR = (1, 1, 1)

# 章鱼参数
OCTOPUS_BODY_RADIUS = 40     # 身体半径
OCTOPUS_TENTACLES = 8        # 触手数量
TENTACLE_LENGTH = 80        # 触手长度
TENTACLE_WAVE_AMPLITUDE = 20 # 触手波动幅度
TENTACLE_BASE_WIDTH = 40     # 触手根部宽度
TENTACLE_TIP_WIDTH = 10       # 触手尖端宽度

# 颜色参数 (RGBA格式，支持透明度渐变)
BODY_COLOR_START = (255, 182, 193, 255)    # 浅粉色
BODY_COLOR_END = (255, 105, 180, 200)      # 深粉色
TENTACLE_COLOR_START = (255, 105, 180, 200) # 深粉色色开始
TENTACLE_COLOR_END = (70, 130, 180, 180)    # 钢蓝色结束

# 移动与物理参数
PET_SPEED = 0.5
MAX_SPEED = 1.5
ACCELERATION = 0.02
DECELERATION = 0.98
ROTATION_SPEED = 0.05       # 降低转向速度，使转向更平滑
WANDER_STRENGTH = 0.01
WALL_REPULSION_STRENGTH = 0.5
WALL_BUFFER = 150           # 边缘缓冲区域
WALL_TURN_SMOOTHNESS = 0.1  # 边缘转向平滑度

# 鼠标交互参数
MOUSE_INTERACTION_RADIUS = 300    # 鼠标交互半径
MOUSE_ATTRACTION_STRENGTH = 0.03  # 鼠标吸引力度
MOUSE_REPULSION_STRENGTH = 0.05   # 鼠标排斥力度
INTERACTION_MODE = "avoid"        # 交互模式: "avoid", "follow", "ignore"

# 交互模式枚举
class InteractionMode(Enum):
    AVOID = "avoid"
    FOLLOW = "follow"
    IGNORE = "ignore"


class DesktopPet:
    def __init__(self):
        pygame.init()
        self.screen_info = pygame.display.Info()
        self.screen_width = self.screen_info.current_w
        self.screen_height = self.screen_info.current_h
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.NOFRAME)
        
        if IS_WINDOWS:
            hwnd = pygame.display.get_wm_info()["window"]
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                   win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*TRANSPARENT_COLOR), 0, win32con.LWA_COLORKEY)
            # 设置窗口为顶层窗口
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                 win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        else:
            self.screen.set_colorkey(TRANSPARENT_COLOR)
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)
        
        # 宠物状态初始化
        self.reset_pet_state()
        
        # 时间变量
        self.t = 0
        self.t_step = np.pi / 120  # 减慢动画速度
        
        # 速度向量
        self.velocity_x = 0
        self.velocity_y = 0
        self.speed = 0
        
        # 交互状态
        self.interaction_mode = InteractionMode(INTERACTION_MODE)
        self.mouse_nearby = False
        self.mouse_distance = 0
        
        # 触手波动参数（每条触手有自己的波动频率和相位）
        self.tentacle_wave_freq = np.random.uniform(1.0, 2.0, OCTOPUS_TENTACLES)  # 每条触手的波动频率
        self.tentacle_wave_phase = np.random.uniform(0, 2*np.pi, OCTOPUS_TENTACLES)  # 每条触手的波动相位
        
        # 触手弯曲参数
        self.tentacle_bend_amount = np.random.uniform(0.2, 0.5, OCTOPUS_TENTACLES)  # 每条触手的弯曲程度
        
        # 触手扭动参数
        self.tentacle_twist_freq = np.random.uniform(0.5, 1.5, OCTOPUS_TENTACLES)  # 每条触手的扭动频率
        self.tentacle_twist_phase = np.random.uniform(0, 2*np.pi, OCTOPUS_TENTACLES)  # 每条触手的扭动相位
        
        # 触手摆动参数
        self.tentacle_swing_freq = np.random.uniform(0.3, 0.8, OCTOPUS_TENTACLES)  # 每条触手的摆动频率
        self.tentacle_swing_phase = np.random.uniform(0, 2*np.pi, OCTOPUS_TENTACLES)  # 每条触手的摆动相位
        
        # 预计算点分布
        self.setup_octopus_points()
        
        print(f"章鱼桌面宠物已启动！交互模式: {self.interaction_mode.value}")
        print("按 'ESC' 键退出。")
        print("按 '1' 键切换为逃避模式")
        print("按 '2' 键切换为跟随模式")
        print("按 '3' 键切换为无视模式")

    def reset_pet_state(self):
        """重置宠物状态"""
        self.pet_x = random.uniform(200, self.screen_width - 200)
        self.pet_y = random.uniform(200, self.screen_height - 200)
        self.pet_angle = random.uniform(0, 2 * np.pi)
        self.pet_target_angle = self.pet_angle
        self.pet_orientation_angle = self.pet_angle
        
        # 初始化速度
        self.velocity_x = PET_SPEED * np.cos(self.pet_angle)
        self.velocity_y = PET_SPEED * np.sin(self.pet_angle)
        self.speed = PET_SPEED

    def setup_octopus_points(self):
        """设置章鱼的点分布，使触手根部粗、尖端细"""
        # 生成更自然的点分布：身体圆形 + 触手
        self.points_type = []  # 0=身体, 1=触手
        self.points_theta = []  # 极坐标角度
        self.points_radius = []  # 极坐标半径
        self.points_size = []    # 点的大小（根据在触手上的位置）
        self.points_tentacle_idx = []  # 触手索引（身体点为-1）
        
        # 1. 身体点 (圆形区域)
        body_points = int(NUM_POINTS * 0.4)
        for i in range(body_points):
            # 在圆形区域内随机分布
            r = random.uniform(0, OCTOPUS_BODY_RADIUS * 0.8)
            theta = random.uniform(0, 2 * np.pi)
            self.points_type.append(0)
            self.points_theta.append(theta)
            self.points_radius.append(r)
            self.points_size.append(DOT_SIZE)  # 身体点大小固定
            self.points_tentacle_idx.append(-1)  # 身体点没有触手索引
        
        # 2. 触手点
        tentacle_points = NUM_POINTS - body_points
        for i in range(tentacle_points):
            # 选择触手
            tentacle_idx = random.randint(0, OCTOPUS_TENTACLES - 1)
            # 触手基础角度
            base_angle = 2 * np.pi * tentacle_idx / OCTOPUS_TENTACLES
            
            # 沿着触手长度分布
            t = random.uniform(0, 1)  # 触手位置 (0=根部, 1=尖端)
            
            # 触手轻微弯曲（使用该触手的弯曲参数）
            bend = np.sin(t * np.pi) * TENTACLE_LENGTH * self.tentacle_bend_amount[tentacle_idx]
            
            # 触手半径（从身体向外延伸）
            r = OCTOPUS_BODY_RADIUS + t * TENTACLE_LENGTH + bend
            
            # 触手角度，根部更贴近身体，外侧更分散
            # 根部区域角度更集中，尖端区域角度更分散
            angle_variation = 0.2 * (1 - t)  # 根部角度变化小，尖端角度变化大
            theta = base_angle + random.uniform(-angle_variation, angle_variation)
            
            # 计算点的大小：根部大，尖端小
            # 使用二次函数使变化更平滑
            size_factor = 1 - t * t  # t²使尖端迅速变小
            point_size = DOT_SIZE * (TENTACLE_BASE_WIDTH * (1 - t) + TENTACLE_TIP_WIDTH * t) / (DOT_SIZE * 10)
            point_size = max(1, point_size)  # 确保至少为1
            
            self.points_type.append(1)
            self.points_theta.append(theta)
            self.points_radius.append(r)
            self.points_size.append(point_size)
            self.points_tentacle_idx.append(tentacle_idx)
        
        # 转换为numpy数组以便向量化操作
        self.points_type = np.array(self.points_type)
        self.points_theta = np.array(self.points_theta)
        self.points_radius = np.array(self.points_radius)
        self.points_size = np.array(self.points_size)
        self.points_tentacle_idx = np.array(self.points_tentacle_idx)

    def handle_events(self):
        """处理事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT or \
               (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                return False
            elif event.type == pygame.KEYDOWN:
                # 切换交互模式
                if event.key == pygame.K_1:
                    self.interaction_mode = InteractionMode.AVOID
                    print("切换为逃避模式")
                elif event.key == pygame.K_2:
                    self.interaction_mode = InteractionMode.FOLLOW
                    print("切换为跟随模式")
                elif event.key == pygame.K_3:
                    self.interaction_mode = InteractionMode.IGNORE
                    print("切换为无视模式")
        return True

    def update_state(self):
        """更新宠物状态"""
        # 处理鼠标交互
        self.handle_mouse_interaction()
        
        # 随机游走
        self.pet_target_angle += random.uniform(-WANDER_STRENGTH, WANDER_STRENGTH)
        
        # 平滑转向
        angle_diff = self.pet_target_angle - self.pet_orientation_angle
        angle_diff = (angle_diff + np.pi) % (2 * np.pi) - np.pi
        self.pet_orientation_angle += angle_diff * ROTATION_SPEED
        
        # 应用速度（带有加速度）
        target_vx = PET_SPEED * np.cos(self.pet_orientation_angle)
        target_vy = PET_SPEED * np.sin(self.pet_orientation_angle)
        
        self.velocity_x = self.velocity_x * DECELERATION + target_vx * ACCELERATION
        self.velocity_y = self.velocity_y * DECELERATION + target_vy * ACCELERATION
        
        # 限制最大速度
        current_speed = np.sqrt(self.velocity_x**2 + self.velocity_y**2)
        if current_speed > MAX_SPEED:
            scale = MAX_SPEED / current_speed
            self.velocity_x *= scale
            self.velocity_y *= scale
        
        # 更新位置
        self.pet_x += self.velocity_x
        self.pet_y += self.velocity_y
        
        # 检查边界并平滑转向
        self.check_bounds_smooth()
        
        # 更新时间
        self.t += self.t_step

    def handle_mouse_interaction(self):
        """处理鼠标交互"""
        if self.interaction_mode == InteractionMode.IGNORE:
            self.mouse_nearby = False
            return
        
        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.pet_x
        dy = mouse_y - self.pet_y
        self.mouse_distance = np.sqrt(dx**2 + dy**2)
        
        self.mouse_nearby = self.mouse_distance < MOUSE_INTERACTION_RADIUS
        
        if self.mouse_nearby and self.mouse_distance > 10:  # 避免除零
            mouse_angle = np.arctan2(dy, dx)
            
            if self.interaction_mode == InteractionMode.AVOID:
                # 逃避模式：转向远离鼠标
                avoidance_angle = mouse_angle + np.pi  # 相反方向
                angle_diff = avoidance_angle - self.pet_target_angle
                angle_diff = (angle_diff + np.pi) % (2 * np.pi) - np.pi
                
                # 距离越近，转向力度越大
                strength = MOUSE_REPULSION_STRENGTH * (1 - self.mouse_distance / MOUSE_INTERACTION_RADIUS)
                self.pet_target_angle += angle_diff * strength
                
            elif self.interaction_mode == InteractionMode.FOLLOW:
                # 跟随模式：转向鼠标方向
                angle_diff = mouse_angle - self.pet_target_angle
                angle_diff = (angle_diff + np.pi) % (2 * np.pi) - np.pi
                
                # 距离越远，跟随力度越大
                strength = MOUSE_ATTRACTION_STRENGTH * (self.mouse_distance / MOUSE_INTERACTION_RADIUS)
                self.pet_target_angle += angle_diff * strength

    def check_bounds_smooth(self):
        """平滑的边界检查"""
        turn_angle = 0
        turn_strength = 0
        
        # 检查四个边界
        if self.pet_x < WALL_BUFFER:
            # 靠近左边界，需要向右转
            turn_angle = 0  # 向右的角度
            turn_strength = max(turn_strength, (WALL_BUFFER - self.pet_x) / WALL_BUFFER)
        
        if self.pet_x > self.screen_width - WALL_BUFFER:
            # 靠近右边界，需要向左转
            turn_angle = np.pi  # 向左的角度
            turn_strength = max(turn_strength, (self.pet_x - (self.screen_width - WALL_BUFFER)) / WALL_BUFFER)
        
        if self.pet_y < WALL_BUFFER:
            # 靠近上边界，需要向下转
            turn_angle = np.pi / 2  # 向下的角度
            turn_strength = max(turn_strength, (WALL_BUFFER - self.pet_y) / WALL_BUFFER)
        
        if self.pet_y > self.screen_height - WALL_BUFFER:
            # 靠近下边界，需要向上转
            turn_angle = -np.pi / 2  # 向上的角度
            turn_strength = max(turn_strength, (self.pet_y - (self.screen_height - WALL_BUFFER)) / WALL_BUFFER)
        
        # 如果有边界转向需求
        if turn_strength > 0:
            # 计算当前方向与目标转向角度的差异
            angle_diff = turn_angle - self.pet_target_angle
            angle_diff = (angle_diff + np.pi) % (2 * np.pi) - np.pi
            
            # 应用平滑转向
            self.pet_target_angle += angle_diff * WALL_TURN_SMOOTHNESS * turn_strength
        
        # 确保宠物不会移出屏幕
        self.pet_x = np.clip(self.pet_x, 10, self.screen_width - 10)
        self.pet_y = np.clip(self.pet_y, 10, self.screen_height - 10)

    def draw(self):
        """绘制章鱼"""
        self.screen.fill(TRANSPARENT_COLOR)
        
        # 计算触手波动 - 每条触手有自己的波动模式
        tentacle_wave = np.zeros(len(self.points_type))
        
        # 为每条触手计算波动
        for tentacle_idx in range(OCTOPUS_TENTACLES):
            # 找到属于这条触手的点
            tentacle_mask = (self.points_tentacle_idx == tentacle_idx)
            
            if np.any(tentacle_mask):
                # 计算每个点在触手上的位置参数
                t_pos = (self.points_radius[tentacle_mask] - OCTOPUS_BODY_RADIUS) / TENTACLE_LENGTH
                t_pos = np.clip(t_pos, 0, 1)
                
                # 基础波动（沿触手传播的波）
                base_wave = np.sin(
                    t_pos * 3 * np.pi +  # 沿触手的相位变化
                    self.t * self.tentacle_wave_freq[tentacle_idx] +  # 时间变化
                    self.tentacle_wave_phase[tentacle_idx]  # 触手特定相位
                )
                
                # 添加触手扭动效果
                twist_wave = np.sin(
                    t_pos * 2 * np.pi +
                    self.t * self.tentacle_twist_freq[tentacle_idx] +
                    self.tentacle_twist_phase[tentacle_idx]
                ) * 0.5
                
                # 添加触手摆动效果（整个触手的左右摆动）
                swing_wave = np.sin(
                    self.t * self.tentacle_swing_freq[tentacle_idx] +
                    self.tentacle_swing_phase[tentacle_idx]
                ) * (1 - t_pos) * 0.3  # 根部摆动大，尖部摆动小
                
                # 组合所有波动效果
                combined_wave = base_wave * 0.7 + twist_wave * 0.3 + swing_wave
                
                # 鼠标接近时增加波动
                if self.mouse_nearby:
                    mouse_factor = 1 + (1 - self.mouse_distance / MOUSE_INTERACTION_RADIUS) * 2
                    combined_wave *= mouse_factor
                
                # 计算波动幅度（尖端波动小，根部波动大）
                wave_amplitude = TENTACLE_WAVE_AMPLITUDE * (1 - t_pos * 0.5)
                tentacle_wave[tentacle_mask] = combined_wave * wave_amplitude
        
        # 计算每个点的实际半径
        radius = self.points_radius.copy()
        # 触手点有波动，身体点没有
        tentacle_mask = (self.points_type == 1)
        radius[tentacle_mask] += tentacle_wave[tentacle_mask] * \
                                 (self.points_radius[tentacle_mask] - OCTOPUS_BODY_RADIUS) / TENTACLE_LENGTH
        
        # 转换为直角坐标（局部坐标）
        local_u = radius * np.cos(self.points_theta)
        local_v = radius * np.sin(self.points_theta)
        
        # 旋转
        angle_correction = -np.pi / 2
        cos_o = np.cos(self.pet_orientation_angle + angle_correction)
        sin_o = np.sin(self.pet_orientation_angle + angle_correction)
        
        rotated_u = local_u * cos_o - local_v * sin_o
        rotated_v = local_u * sin_o + local_v * cos_o
        
        # 平移
        screen_u = rotated_u + self.pet_x
        screen_v = rotated_v + self.pet_y
        
        # 绘制每个点，根据类型使用不同颜色
        for i in range(len(self.points_type)):
            # 计算颜色渐变
            if self.points_type[i] == 0:  # 身体点
                # 根据半径确定颜色插值
                t_color = self.points_radius[i] / (OCTOPUS_BODY_RADIUS * 0.8)
                t_color = min(1.0, max(0.0, t_color))
                
                r = int(BODY_COLOR_START[0] * (1 - t_color) + BODY_COLOR_END[0] * t_color)
                g = int(BODY_COLOR_START[1] * (1 - t_color) + BODY_COLOR_END[1] * t_color)
                b = int(BODY_COLOR_START[2] * (1 - t_color) + BODY_COLOR_END[2] * t_color)
                a = int(BODY_COLOR_START[3] * (1 - t_color) + BODY_COLOR_END[3] * t_color)
                
                # 添加时间变化
                time_variation = np.sin(self.t * 0.5) * 10
                r = min(255, max(0, r + time_variation))
                g = min(255, max(0, g - time_variation * 0.5))
                
            else:  # 触手点
                # 根据触手位置确定颜色插值
                t_color = (self.points_radius[i] - OCTOPUS_BODY_RADIUS) / TENTACLE_LENGTH
                t_color = min(1.0, max(0.0, t_color))
                
                r = int(TENTACLE_COLOR_START[0] * (1 - t_color) + TENTACLE_COLOR_END[0] * t_color)
                g = int(TENTACLE_COLOR_START[1] * (1 - t_color) + TENTACLE_COLOR_END[1] * t_color)
                b = int(TENTACLE_COLOR_START[2] * (1 - t_color) + TENTACLE_COLOR_END[2] * t_color)
                a = int(TENTACLE_COLOR_START[3] * (1 - t_color) + TENTACLE_COLOR_END[3] * t_color)
                
                # 添加时间变化
                time_variation = np.sin(self.t * 2 + self.points_theta[i]) * 15
                b = min(255, max(0, b + time_variation))
                g = min(255, max(0, g + time_variation * 0.3))
            
            # 鼠标接近时增加透明度变化
            if self.mouse_nearby:
                pulse = np.sin(self.t * 3) * 20
                a = min(255, max(100, a + pulse))
            
            # 创建颜色
            color = (r, g, b, a)
            
            # 绘制点
            if a > 10:  # 只绘制足够透明的点
                # 根据计算的点大小绘制圆点
                point_size = max(1, int(self.points_size[i]))
                point_surface = pygame.Surface((point_size * 2, point_size * 2), pygame.SRCALPHA)
                pygame.draw.circle(point_surface, color, (point_size, point_size), point_size)
                self.screen.blit(point_surface, (screen_u[i] - point_size, screen_v[i] - point_size))
        
        # 绘制交互状态提示
        mode_text = self.font.render(f"模式: {self.interaction_mode.value}", True, (255, 255, 255))
        self.screen.blit(mode_text, (10, 10))
        
        if self.mouse_nearby:
            distance_text = self.font.render(f"鼠标距离: {int(self.mouse_distance)}", True, (255, 255, 255))
            self.screen.blit(distance_text, (10, 40))
        
        pygame.display.flip()

    def run(self):
        """运行主循环"""
        running = True
        while running:
            running = self.handle_events()
            self.update_state()
            self.draw()
            self.clock.tick(TARGET_FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    pet = DesktopPet()
    pet.run()