'''
    Initially written by Ming Hsiao in MATLAB
    Adapted to Python by Akash Sharma (akashsharma@cmu.edu), 2020
    Updated by Wei Dong (weidong@andrew.cmu.edu), 2021
'''

import numpy as np
import re
import matplotlib.pyplot as plt
np.set_printoptions(suppress=True, threshold=np.inf, linewidth=np.inf)


def draw_cov_ellipse(mu, cov, color):
    """
    Draws an ellipse in plt canvas.

    \param mu Mean of a Gaussian
    \param cov Covariance of a Gaussian
    \param color Color in plt format, e.g. 'b' for blue, 'r' for red.
    """
    U, s, Vh = np.linalg.svd(cov)
    a, b = s[0], s[1]
    vx, vy = U[0, 0], U[0, 1]
    theta = np.arctan2(vy, vx)
    R = np.array([[np.cos(theta), -np.sin(theta)],
                  [np.sin(theta), np.cos(theta)]])
    phi = np.arange(0, 2 * np.pi, np.pi / 50)
    rot = []
    for i in range(100):
        rect = (np.array(
            [3 * np.sqrt(a) * np.cos(phi[i]),
             3 * np.sqrt(b) * np.sin(phi[i])]))[:, None]
        rot.append(R @ rect + mu)

    rot = np.asarray(rot)
    plt.plot(rot[:, 0], rot[:, 1], c=color, linewidth=0.75)


def draw_traj_and_pred(X, P):
    """ Draw trajectory for Predicted state and Covariance

    :X: Prediction vector
    :P: Prediction Covariance matrix
    :returns: None

    """
    draw_cov_ellipse(X[0:2], P[0:2, 0:2], 'm')
    plt.draw()
    plt.waitforbuttonpress(0)


def draw_traj_and_map(X, last_X, P, t):
    """Draw Trajectory and map

    :X: Current state
    :last_X: Previous state
    :P: Covariance
    :t: timestep
    :returns: None

    """
    plt.ion()
    draw_cov_ellipse(X[0:2], P[0:2, 0:2], 'b')
    plt.plot([last_X[0], X[0]], [last_X[1], X[1]], c='b', linewidth=0.75)
    plt.plot(X[0], X[1], '*b')

    if t == 0:
        for k in range(6):
            draw_cov_ellipse(
                X[3 + k * 2:3 + k * 2 + 2], P[3 + k * 2:3 + 2 * k + 2,
                                              3 + 2 * k:3 + 2 * k + 2], 'r')
    else:
        for k in range(6):
            draw_cov_ellipse(
                X[3 + k * 2:3 + k * 2 + 2], P[3 + 2 * k:3 + 2 * k + 2,
                                              3 + 2 * k:3 + 2 * k + 2], 'g')

    plt.draw()
    plt.waitforbuttonpress(0)


def warp2pi(angle_rad):
    """
    TODO: warps an angle in [-pi, pi]. Used in the update step.

    \param angle_rad Input angle in radius
    \return angle_rad_warped Warped angle to [-\pi, \pi].
    
    """
    angle_rad = angle_rad - 2 * np.pi * np.floor((angle_rad + np.pi) / (2 * np.pi))
    return angle_rad


def init_landmarks(init_measure, init_measure_cov, init_pose, init_pose_cov):
    '''
    TODO: initialize landmarks given the initial poses and measurements with their covariances
    \param init_measure Initial measurements in the form of (beta0, l0, beta1, l1, ...).
    \param init_measure_cov Initial covariance matrix of shape (2, 2) per landmark given parameters.
    \param init_pose Initial pose vector of shape (3, 1).
    \param init_pose_cov Initial pose covariance of shape (3, 3) given parameters.

    \return k Number of landmarks.
    \return landmarks Numpy array of shape (2k, 1) for the state.
    \return landmarks_cov Numpy array of shape (2k, 2k) for the uncertainty.
    '''
    # There are 6 landmarks
    # data.txt gives [beta1, r1,beta2,r2,...] for each landmark and then [d, alpha] for each control
    # the lines are in sequential time order 

    k = init_measure.shape[0] // 2

    landmarks = np.zeros((2 * k, 1))
    landmarks_cov = np.zeros((2 * k, 2 * k))

    x, y, theta = init_pose.flatten()

    for i in range(k):
        beta, r = init_measure[2*i,0], init_measure[2*i+1,0]
        global_beta = float(warp2pi(beta + theta))
       
        lx = x + r * np.cos(global_beta)
        ly = y + r * np.sin(global_beta)

        landmarks[2*i,0] = lx
        landmarks[2*i+1,0] = ly

        # This will be a 2k*3 matrix and is the Jacobian of the landmark coordinates to the robot pose
        Jp = np.array([[1, 0, -r * np.sin(global_beta)],
                        [0, 1, r * np.cos(global_beta)]])

        # This will end up as a 2k*2k matrix and is the Jacobian of the landmark coordinates to bearing and range
        Jk = np.array([[-r * np.sin(global_beta), np.cos(global_beta)],
                      [r * np.cos(global_beta), np.sin(global_beta)]])
        
        
        # Combine the two matricies
        J = np.hstack((Jp, Jk))

        # Combine the inital pose covariance and the measurement covariance
        P = np.block([[init_pose_cov, np.zeros((3, 2))],
                        [np.zeros((2, 3)), init_measure_cov]])


        landmarks_cov[2*i:2*i+2, 2*i:2*i+2] = J @ P @ J.T
    

    return k, landmarks, landmarks_cov


def predict(X, P, control, control_cov, k):
    '''
    TODO: predict step in EKF SLAM with derived Jacobians.
    \param X State vector of shape (3 + 2k, 1) stacking pose and landmarks.
    \param P Covariance matrix of shape (3 + 2k, 3 + 2k) for X.
    \param control Control signal of shape (2, 1) in the polar space that moves the robot.
    \param control_cov Control covariance of shape (3, 3) in the (x, y, theta) space given the parameters.
    \param k Number of landmarks.

    \return X_pre Predicted X state of shape (3 + 2k, 1).
    \return P_pre Predicted P covariance of shape (3 + 2k, 3 + 2k).
    '''
    # control comes in as [d,alpha]
    d , alpha = control[0,0], control[1,0]
    x_t, y_t, theta_t = X[0,0], X[1,0], X[2,0]
    X_pre = np.zeros((3+2*k,1))
    P_pre = np.zeros((3+2*k,3+2*k))

    # This is the predicted pose
    # Predicted x
    X_pre[0] = x_t + d * np.cos(theta_t)
    # Predicted y
    X_pre[1] = y_t + d * np.sin(theta_t)
    # Predicted theta
    X_pre[2] = warp2pi(theta_t + alpha)
    # Add the landmarks to the predicted state
    X_pre[3:] = X[3:]

    R = np.block([[control_cov, np.zeros((3,2*k))],
                    [np.zeros((2*k,3)), np.zeros((2*k,2*k))]])

    # This is the jacobian of the pose prediction to the pose
    Gt = np.array([[1, 0, -d * np.sin(theta_t)],
                [0, 1, d * np.cos(theta_t)],
                [0, 0, 1]])
    # Adding zeros and identity matrix to the jacobians to account for the landmarks
    Gt = np.block([[Gt, np.zeros((3,2*k))],
                    [np.zeros((2*k,3)), np.eye(2*k)]])
    
    # This is the jacobian of the pose prediction to the error in the control
    Bt = np.array([[np.cos(theta_t), -np.sin(theta_t), 0],
                [np.sin(theta_t), np.cos(theta_t), 0],
                [0, 0, 1]])
    
    # Adding zeros and identity matrix to the jacobians to account for the landmarks
    Bt = np.block([[Bt, np.zeros((3,2*k))],
                    [np.zeros((2*k,3)), np.eye(2*k)]])
    
    # print('This is Gt')
    # print(Gt)
    # print('This is B')
    # print(B)


    
    P_pre = Gt @ P @ Gt.T + Bt @ R @ Bt.T

    # print('This is P_pre')
    # print(P_pre)

    return X_pre, P_pre


def update(X_pre, P_pre, measure, measure_cov, k):
    '''
    TODO: update step in EKF SLAM with derived Jacobians.
    \param X_pre Predicted state vector of shape (3 + 2k, 1) from the predict step.
    \param P_pre Predicted covariance matrix of shape (3 + 2k, 3 + 2k) from the predict step.
    \param measure Measurement signal of shape (2k, 1).
    \param measure_cov Measurement covariance of shape (2, 2) per landmark given the parameters.
    \param k Number of landmarks.

    \return X Updated X state of shape (3 + 2k, 1).
    \return P Updated P covariance of shape (3 + 2k, 3 + 2k).
    '''

    H = np.zeros((2*k, 3+2*k))
    measurement = np.zeros((2*k, 1))
    x, y, theta = X_pre[0,0], X_pre[1,0], X_pre[2,0]


    for i in range(k):
        lx, ly = X_pre[3+2*i,0], X_pre[3+2*i+1,0]
        dx = lx - x
        dy = ly - y
        r = np.sqrt(dx**2 + dy**2)

        Hp_i = np.array([[dy/r**2, -dx/r**2, -1],
                        [-dx/r, -dy/r, 0]])
        H[2*i:2*i+2, 0:3] = Hp_i
        Hl_i = np.array([[-dy/r**2, dx/r**2],
                        [dx/r, dy/r]])
        H[2*i:2*i+2, 3+2*i:3+2*i+2] = Hl_i
        # print('This is H')
        # print(H)

        measurement[2*i] = warp2pi(np.arctan2(dy, dx) - theta)
        measurement[2*i+1] = r

    Q = np.kron(np.eye(k), measure_cov)
    # print('This is Q')
    # print(Q)
    # print('This is H')
    # print(H)
    

    K = P_pre @ H.T @ np.linalg.inv(H @ P_pre @ H.T + Q)
    X_pre = X_pre + K @ (measure - measurement)
    P_pre = (np.eye(3+2*k) - K @ H) @ P_pre


    return X_pre, P_pre


def evaluate(X, P, k):
    '''
    TODO: evaluate the performance of EKF SLAM.
    1) Plot the results.
    2) Compute and print the Euclidean and Mahalanobis distance given X, P, and the ground truth (provided in the function).
    \param X State vector of shape (3 + 2k, 1) stacking pose and landmarks.
    \param P Covariance matrix of shape (3 + 2k, 3 + 2k) for X.

    \return None
    '''
    l_true = np.array([3, 6, 3, 12, 7, 8, 7, 14, 11, 6, 11, 12], dtype=float)
    plt.scatter(l_true[0::2], l_true[1::2])
    plt.draw()
    plt.waitforbuttonpress(0)

    l_pred = X[3:]

    # Euclidean distances
    euclidean_distances = np.sqrt(((l_pred.reshape(-1, 2) - l_true.reshape(-1, 2))**2).sum(axis=1))
    total_euclidean = np.sum(euclidean_distances)
    print(f'Euclidean distance for each landmark: {euclidean_distances}')
    print(f'Total Euclidean distance: {total_euclidean}')

    # Mahalanobis distances
    mahal_distances = []

    for i in range(k):
        l = l_pred[2*i:2*i+2]
        l_cov = P[3+2*i:3+2*i+2, 3+2*i:3+2*i+2]
        mahal_distances.append(np.sqrt(l.T @ np.linalg.inv(l_cov) @ l))

    mahal_distances = np.array(mahal_distances).flatten()
    print(f'Mahalanobis distances for each landmark: {mahal_distances}')
    print(f'Total Mahalanobis distance: {np.sum(mahal_distances)}')




def main():
    # TEST: Setup uncertainty parameters
    sig_x = 0.25
    sig_y = 0.1
    sig_alpha = 0.1
    sig_beta = 0.01
    sig_r = 0.08


    # Generate variance from standard deviation
    sig_x2 = sig_x**2
    sig_y2 = sig_y**2
    sig_alpha2 = sig_alpha**2
    sig_beta2 = sig_beta**2
    sig_r2 = sig_r**2

    # Open data file and read the initial measurements
    data_file = open("data/data.txt")
    line = data_file.readline()
    fields = re.split('[\t ]', line)[:-1]
    arr = np.array([float(field) for field in fields])
    measure = np.expand_dims(arr, axis=1)
    t = 1

    # Setup control and measurement covariance
    control_cov = np.diag([sig_x2, sig_y2, sig_alpha2])
    measure_cov = np.diag([sig_beta2, sig_r2])

    # Setup the initial pose vector and pose uncertainty
    pose = np.zeros((3, 1))
    pose_cov = np.diag([0.02**2, 0.02**2, 0.1**2])

    ##########
    # TODO: initialize landmarks
    k, landmark, landmark_cov = init_landmarks(measure, measure_cov, pose,
                                               pose_cov)

    # Setup state vector X by stacking pose and landmark states
    # Setup covariance matrix P by expanding pose and landmark covariances
    X = np.vstack((pose, landmark))
    P = np.block([[pose_cov, np.zeros((3, 2 * k))],
                  [np.zeros((2 * k, 3)), landmark_cov]])

    # Plot initial state and covariance
    last_X = X
    draw_traj_and_map(X, last_X, P, 0)

    # Core loop: sequentially process controls and measurements
    for line in data_file:
        fields = re.split('[\t ]', line)[:-1]
        arr = np.array([float(field) for field in fields])

        # Control
        if arr.shape[0] == 2:
            print(f'{t}: Predict step')
            d, alpha = arr[0], arr[1]
            control = np.array([[d], [alpha]])

            ##########
            # TODO: predict step in EKF SLAM
            # print('Got to predict step')
            X_pre, P_pre = predict(X, P, control, control_cov, k)

            draw_traj_and_pred(X_pre, P_pre)

        # Measurement
        else:
            print(f'{t}: Update step')
            measure = np.expand_dims(arr, axis=1)

            ##########
            # TODO: update step in EKF SLAM
            X, P = update(X_pre, P_pre, measure, measure_cov, k)

            draw_traj_and_map(X, last_X, P, t)
            last_X = X
            t += 1

    # EVAL: Plot ground truth landmarks and analyze distances
    evaluate(X, P, k)


if __name__ == "__main__":
    main()
