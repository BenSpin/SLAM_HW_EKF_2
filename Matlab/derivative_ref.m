% Define symbolic variables
syms x_t y_t theta_t l_x l_y real

% Define the robot's pose and landmark position
p_t = [x_t; y_t; theta_t];
l = [l_x; l_y];


r = sqrt((l_x - x_t)^2 + (l_y - y_t)^2);
phi = atan2(l_y - y_t, l_x - x_t) - theta_t;


H_r = [diff(r, x_t), diff(r, y_t), diff(r, theta_t);
       diff(phi, x_t), diff(phi, y_t), diff(phi, theta_t)];


H_r_simplified = simplify(H_r);


disp(H_r_simplified);
