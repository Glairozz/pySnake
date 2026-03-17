import pygame
import random
import math
import json
import os

pygame.init()

WIDTH, HEIGHT = 600, 650
GRID_SIZE = 25
GRID_WIDTH = WIDTH // GRID_SIZE
GRID_HEIGHT = HEIGHT // GRID_SIZE

COLORS = {
    'bg': (15, 15, 25),
    'bg_light': (25, 25, 40),
    'grid': (35, 35, 55),
    'snake_head': (120, 255, 120),
    'snake_body': (70, 220, 70),
    'snake_body_light': (90, 240, 90),
    'snake_shadow': (40, 140, 40),
    'food': (255, 70, 70),
    'food_glow': (255, 120, 120),
    'food_inner': (255, 150, 150),
    'text': (230, 230, 230),
    'accent': (100, 200, 255),
    'accent_glow': (100, 200, 255, 100),
    'warning': (255, 180, 50),
    'particle_food': (255, 100, 100),
    'particle_snake': (100, 255, 100),
}

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Snake")
clock = pygame.time.Clock()

title_font = pygame.font.Font(None, 56)
font = pygame.font.Font(None, 32)
small_font = pygame.font.Font(None, 22)
ui_font = pygame.font.Font(None, 20)

HIGH_SCORE_FILE = "highscore.json"

def load_high_score():
    try:
        if os.path.exists(HIGH_SCORE_FILE):
            with open(HIGH_SCORE_FILE, 'r') as f:
                return json.load(f).get('high_score', 0)
    except:
        pass
    return 0

def save_high_score(score):
    try:
        with open(HIGH_SCORE_FILE, 'w') as f:
            json.dump({'high_score': score}, f)
    except:
        pass

class Particle:
    def __init__(self, x, y, color, velocity=None):
        self.x = x
        self.y = y
        self.color = color
        self.life = 1.0
        self.decay = random.uniform(0.02, 0.04)
        self.size = random.randint(3, 8)
        if velocity:
            self.vx, self.vy = velocity
        else:
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1, 3)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        return self.life > 0

    def draw(self, surface):
        if self.life > 0:
            alpha = int(self.life * 255)
            color = (*self.color[:3], alpha) if len(self.color) == 4 else self.color
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.size * self.life))

class Snake:
    def __init__(self):
        self.body = [(GRID_WIDTH // 2, GRID_HEIGHT // 2 - 1),
                     (GRID_WIDTH // 2, GRID_HEIGHT // 2),
                     (GRID_WIDTH // 2, GRID_HEIGHT // 2 + 1)]
        self.direction = (0, -1)
        self.next_direction = (0, -1)
        self.grow = False

    def move(self):
        self.direction = self.next_direction
        head = self.body[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        
        if (new_head[0] < 0 or new_head[0] >= GRID_WIDTH or
            new_head[1] < 0 or new_head[1] >= GRID_HEIGHT or
            new_head in self.body):
            return False
        
        self.body.insert(0, new_head)
        
        if not self.grow:
            self.body.pop()
        else:
            self.grow = False
        
        return True

    def change_direction(self, dx, dy):
        if (dx, dy) != (-self.direction[0], -self.direction[1]):
            self.next_direction = (dx, dy)

    def get_head_position(self):
        return self.body[0]

    def draw(self):
        for i, segment in enumerate(self.body):
            x = segment[0] * GRID_SIZE
            y = segment[1] * GRID_SIZE
            
            if i == 0:
                pygame.draw.rect(screen, COLORS['snake_head'], 
                               (x + 3, y + 3, GRID_SIZE - 6, GRID_SIZE - 6), border_radius=8)
                
                pygame.draw.rect(screen, COLORS['bg'], 
                               (x + 5, y + 5, GRID_SIZE - 10, GRID_SIZE - 10), border_radius=6)
                
                eye_size = 5
                eye_offset = GRID_SIZE // 3
                eye_color = (20, 20, 30)
                
                dx, dy = self.direction
                if dx == 1:
                    ex1, ey1 = x + GRID_SIZE - eye_offset - 2, y + eye_offset
                    ex2, ey2 = x + GRID_SIZE - eye_offset - 2, y + GRID_SIZE - eye_offset - 4
                elif dx == -1:
                    ex1, ey1 = x + eye_offset - 2, y + eye_offset
                    ex2, ey2 = x + eye_offset - 2, y + GRID_SIZE - eye_offset - 4
                elif dy == -1:
                    ex1, ey1 = x + eye_offset, y + eye_offset - 2
                    ex2, ey2 = x + GRID_SIZE - eye_offset - 4, y + eye_offset - 2
                else:
                    ex1, ey1 = x + eye_offset, y + GRID_SIZE - eye_offset - 4
                    ex2, ey2 = x + GRID_SIZE - eye_offset - 4, y + GRID_SIZE - eye_offset - 4
                
                pygame.draw.circle(screen, eye_color, (ex1, ey1), eye_size)
                pygame.draw.circle(screen, eye_color, (ex2, ey2), eye_size)
                
            else:
                alpha = max(0.3, 1 - (i / len(self.body)) * 0.5)
                color = COLORS['snake_body']
                pygame.draw.rect(screen, color, 
                               (x + 4, y + 4, GRID_SIZE - 8, GRID_SIZE - 8), border_radius=6)
                pygame.draw.rect(screen, COLORS['snake_shadow'], 
                               (x + 4, y + GRID_SIZE - 10, GRID_SIZE - 8, 4), border_radius=3)

class Food:
    def __init__(self):
        self.position = (0, 0)
        self.spawn()
        self.animation_offset = 0

    def spawn(self):
        self.position = (random.randint(0, GRID_WIDTH - 1),
                        random.randint(0, GRID_HEIGHT - 1))

    def draw(self):
        x = self.position[0] * GRID_SIZE
        y = self.position[1] * GRID_SIZE
        
        pulse = abs(pygame.time.get_ticks() % 800 - 400) / 400
        glow_size = int(GRID_SIZE + pulse * 6)
        glow_offset = (glow_size - GRID_SIZE) // 2
        
        glow_surface = pygame.Surface((glow_size + 10, glow_size + 10), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (*COLORS['food_glow'], int(50 + pulse * 30)),
                        (5, 5, glow_size, glow_size), border_radius=10)
        screen.blit(glow_surface, (x - 5 - glow_offset, y - 5 - glow_offset))
        
        pygame.draw.rect(screen, COLORS['food'],
                        (x + 4, y + 4, GRID_SIZE - 8, GRID_SIZE - 8), border_radius=8)
        
        inner_size = GRID_SIZE - 14
        if inner_size > 0:
            pygame.draw.rect(screen, COLORS['food_inner'],
                           (x + 7, y + 7, inner_size, inner_size), border_radius=4)

def draw_grid():
    for x in range(0, WIDTH, GRID_SIZE):
        pygame.draw.line(screen, COLORS['grid'], (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, COLORS['grid'], (0, y), (WIDTH, y), 1)

def draw_header(score, high_score):
    pygame.draw.rect(screen, COLORS['bg_light'], (0, 0, WIDTH, 50))
    pygame.draw.line(screen, COLORS['grid'], (0, 50), (WIDTH, 50), 2)
    
    title = font.render("SNAKE", True, COLORS['snake_head'])
    screen.blit(title, (20, 12))
    
    score_text = small_font.render(f"Score: {score}", True, COLORS['text'])
    screen.blit(score_text, (WIDTH // 2 - 40, 15))
    
    high_text = small_font.render(f"Best: {high_score}", True, COLORS['accent'])
    screen.blit(high_text, (WIDTH - 120, 15))

def draw_ui_elements(score, high_score, paused):
    draw_header(score, high_score)
    if paused:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))
        
        paused_text = title_font.render("PAUSED", True, COLORS['accent'])
        rect = paused_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(paused_text, rect)
        
        hint = small_font.render("Press P to resume", True, COLORS['text'])
        rect2 = hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40))
        screen.blit(hint, rect2)

def draw_start_screen(high_score):
    screen.fill(COLORS['bg'])
    draw_grid()
    
    title = title_font.render("SNAKE", True, COLORS['snake_head'])
    title_shadow = title_font.render("SNAKE", True, COLORS['snake_shadow'])
    screen.blit(title_shadow, (WIDTH // 2 - title.get_width() // 2 + 3, HEIGHT // 2 - 80 + 3))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 80))
    
    subtitle = font.render("Press any arrow key to start", True, COLORS['text'])
    screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, HEIGHT // 2))
    
    controls = ui_font.render("Arrow Keys or WASD to move  |  P to pause", True, (100, 100, 120))
    screen.blit(controls, (WIDTH // 2 - controls.get_width() // 2, HEIGHT // 2 + 50))
    
    if high_score > 0:
        hs = font.render(f"High Score: {high_score}", True, COLORS['accent'])
        screen.blit(hs, (WIDTH // 2 - hs.get_width() // 2, HEIGHT // 2 + 100))
    
    draw_header(0, high_score)
    pygame.display.flip()

def draw_game_over(score, high_score, is_new_high):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    
    go_text = title_font.render("GAME OVER", True, COLORS['food'])
    screen.blit(go_text, (WIDTH // 2 - go_text.get_width() // 2, HEIGHT // 2 - 60))
    
    score_text = font.render(f"Score: {score}", True, COLORS['text'])
    screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, HEIGHT // 2))
    
    if is_new_high:
        new_hs = font.render("New High Score!", True, COLORS['accent'])
        screen.blit(new_hs, (WIDTH // 2 - new_hs.get_width() // 2, HEIGHT // 2 + 40))
    
    restart = small_font.render("Press SPACE to restart", True, (100, 100, 120))
    screen.blit(restart, (WIDTH // 2 - restart.get_width() // 2, HEIGHT // 2 + 90))
    
    pygame.display.flip()

def main():
    snake = Snake()
    food = Food()
    particles = []
    score = 0
    high_score = load_high_score()
    speed = 12
    base_speed = 12
    
    game_state = "start"
    paused = False
    running = True
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                
                if game_state == "start":
                    direction_map = {
                        pygame.K_UP: (0, -1),
                        pygame.K_DOWN: (0, 1),
                        pygame.K_LEFT: (-1, 0),
                        pygame.K_RIGHT: (1, 0),
                        pygame.K_w: (0, -1),
                        pygame.K_s: (0, 1),
                        pygame.K_a: (-1, 0),
                        pygame.K_d: (1, 0),
                    }
                    if event.key in direction_map:
                        snake.direction = direction_map[event.key]
                        snake.next_direction = direction_map[event.key]
                        game_state = "playing"
                
                elif game_state == "playing":
                    if event.key == pygame.K_p or event.key == pygame.K_ESCAPE:
                        paused = not paused
                    
                    direction_map = {
                        pygame.K_UP: (0, -1),
                        pygame.K_DOWN: (0, 1),
                        pygame.K_LEFT: (-1, 0),
                        pygame.K_RIGHT: (1, 0),
                        pygame.K_w: (0, -1),
                        pygame.K_s: (0, 1),
                        pygame.K_a: (-1, 0),
                        pygame.K_d: (1, 0),
                    }
                    if event.key in direction_map:
                        snake.change_direction(*direction_map[event.key])
                
                elif game_state == "gameover":
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        snake = Snake()
                        food.spawn()
                        score = 0
                        speed = base_speed
                        paused = False
                        game_state = "playing"

        if game_state == "start":
            draw_start_screen(high_score)
        
        elif game_state == "playing":
            if not paused:
                if snake.direction != (0, 0):
                    if not snake.move():
                        is_new = score > high_score
                        if is_new:
                            high_score = score
                            save_high_score(high_score)
                        game_state = "gameover"
                        draw_game_over(score, high_score, is_new)
                        continue

                    head_x, head_y = snake.get_head_position()
                    if (head_x, head_y) == food.position:
                        snake.grow = True
                        fx, fy = food.position
                        for _ in range(12):
                            particles.append(Particle(
                                fx * GRID_SIZE + GRID_SIZE // 2,
                                fy * GRID_SIZE + GRID_SIZE // 2,
                                COLORS['particle_food']
                            ))
                        food.spawn()
                        score += 10
                        if score % 50 == 0:
                            speed = min(speed + 2, 25)

            screen.fill(COLORS['bg'])
            draw_grid()
            food.draw()
            snake.draw()
            
            particles = [p for p in particles if p.update()]
            for p in particles:
                p.draw(screen)
            
            draw_ui_elements(score, high_score, paused)
            pygame.display.flip()
            clock.tick(speed if not paused else 30)
        
        elif game_state == "gameover":
            clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()
