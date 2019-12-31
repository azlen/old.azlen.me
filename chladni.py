from sympy import *
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import LinearSegmentedColormap

x,xi,ny,c = symbols('x xi ny c')
w_e,h_e = symbols('w_e h_e')
expr_n = []
expr_n.append(1/2.0*(1.0-x))
expr_n.append(1/2.0*(x+1.0))

J = Matrix([[w_e/2, 0], [0, h_e/2]])
Jinv = J.inv()
Jdet = J.det()

#Evaluate the 2D shape functions
expr_nn = []
expr_dnnx = []
expr_dnny = []
for a in range(0,2):
    for b in range(0,2):
        expr_nn.append(expr_n[b].subs(x,xi)*expr_n[a].subs(x,ny))

NN = Matrix(expr_nn)
dNNx = NN.applyfunc(lambda a: Jinv[0,0]*diff(a,xi)+Jinv[0,1]*diff(a,ny))
dNNy = NN.applyfunc(lambda a: Jinv[1,0]*diff(a,xi)+Jinv[1,1]*diff(a,ny))

#PLate dimensions
w_m = 0.22
h_m = 0.22

#Elements in each direction
w_i = 30
h_i = 30

#Calc element size
element_w = w_m/w_i
element_h = h_m/h_i
       
#PLATE MATERIAL PROPERTIES
t = 0.001
rho = 7859
poisson = 0.29
E = 205000000000
G = E/(2*(1+poisson))
k = 5/6.0
q = 1000

Db = E*(t**3)/(12*(1-poisson**2))*Matrix([[1,poisson,0],[poisson,1,0],[0,0,(1-poisson)]])
Ds = k*G*t*Matrix([[1,0],[0,1]])

expr_ke = zeros(12,12)
expr_km = zeros(12,12)
expr_f = zeros(12,1)

#Element stiffness matrix
def Bb(ix):
    return Matrix([[0,dNNx[ix],0],[0,0,dNNy[ix]],[0,dNNy[ix],dNNx[ix]]])
def Bs(ix):
    return Matrix([[dNNx[ix],-NN[ix],0],[dNNy[ix],0,-NN[ix]]])

Bb_all = zeros(3,0)
Bs_all = zeros(2,0)

for i in range(0,4):
    Bb_all = Bb_all.row_join(Bb(i))
    Bs_all = Bs_all.row_join(Bs(i))
    

keb = Bb_all.transpose()*Db*Bb_all
kes = Bs_all.transpose()*Ds*Bs_all

expr_ke += keb
expr_ke += kes
expr_ke = expr_ke.applyfunc(lambda a: Jdet*integrate(integrate(a,(xi,-1,1)),(ny,-1,1)))

#Element mass matrix
for i in range(0,4):
    for j in range(0,4):
        Moo = Jdet*integrate(integrate(rho*t*NN[i]*NN[j],(xi,-1,1)),(ny,-1,1))
        Maa = Jdet*integrate(integrate(rho*t**3/12*NN[i]*NN[j],(xi,-1,1)),(ny,-1,1))
        
        expr_km[i*3,j*3] = Moo
        expr_km[i*3+1,j*3+1] = Maa
        expr_km[i*3+2,j*3+2] = Maa

#Element force vector
for i in range(0,4):
    expr_f[i*3] = q*integrate(integrate(NN[i]*NN[j],(xi,-1,1)),(ny,-1,1))

print("Element k- and m-matrix symbolic evaluation done")

#Evaluate element k- and m-matrix numerically
ke = expr_ke.applyfunc(lambda a: a.subs([(w_e,element_w),(h_e,element_h)]).evalf())
km = expr_km.applyfunc(lambda a: a.subs([(w_e,element_w),(h_e,element_h)]).evalf())
f = expr_f.applyfunc(lambda a: a.subs([(w_e,element_w),(h_e,element_h)]).evalf())

print("Element k- and m-matrix numeric evaluation done")

#Global nodes
nDOF = ((w_i+1)*(h_i+1)*3)

#Local-Global transformation
loc_glob = []
for el_i in range(0,w_i*h_i):
    loc_glob.append([])
    row = el_i//w_i
    col = el_i%w_i
    for el_r in range(0,2):
        loc_glob[-1] = np.append(loc_glob[-1],np.sum([range(0,6),np.multiply(ones(1,6),(row+el_r)*((w_i+1)*3)+col*3)],axis=0))

#Global matrices
K = np.zeros((nDOF,nDOF))
M = np.zeros((nDOF,nDOF))
F = np.zeros((nDOF,1))

#Make global K- and M-matrix
for el_i in range(0,w_i*h_i):
    for a in range(0,12):
        for b in range(0,12):
            K[loc_glob[el_i][a]][loc_glob[el_i][b]] += ke[a,b]
            M[loc_glob[el_i][a]][loc_glob[el_i][b]] += km[a,b]
        F[loc_glob[el_i][a]][0] += f[a]

print("Global K- and M-matrix addition done")

#Apply boundary conditions, allow sliding along a vertical axis in the middle
ix_i = int(nDOF/3/2)*3 #The middle vertical DOF
ix = range(ix_i+1,ix_i+3)
K = np.delete(K, ix, axis=0)
K = np.delete(K, ix, axis=1)
M = np.delete(M, ix, axis=0)
M = np.delete(M, ix, axis=1)
F = np.delete(F, ix, axis=0)
F = np.delete(F, ix, axis=1)

#Vertical force in the middle
F[:] = 0
F[ix_i] = 1


ssf = []
ssmag = []
def generatePattern(freq, filename):
    #current_f = 160**(1.01+i/400.0)
    current_f = freq
    omega = 2*np.pi*current_f
        
    eplo_p = np.dot(np.linalg.inv(-omega**2*M+K),F)

    #Add back zeros (boundaries)
    eplo = np.append(eplo_p[0:ix[0]],[0]*(len(ix)))
    eplo = np.append(eplo, eplo_p[ix[0]:])
    
    #Displacements only
    eplo = eplo[0::3]
    eplo = np.reshape(eplo,((h_i+1),(w_i+1)))
    
    X = np.linspace(0,w_m,w_i+1)
    Y = np.linspace(0,h_m,h_i+1)
    X,Y = np.meshgrid(X,Y)
    Z = np.real(eplo) 
    ssf.append(current_f)
    ssmag.append(np.sqrt(np.mean(np.square(Z))))
    #Z = np.multiply(1/np.max(np.abs(Z)),Z)

    
    bt_cm = LinearSegmentedColormap.from_list("test", ((0,0,0,1), (0,0,0,0.9), (0,0,0,0), (0,0,0,0)), N=127)
    
    fig, ax = plt.subplots() #RdBu, bone, etc (gg python colormaps)
    Z_im = np.sqrt(np.sqrt(np.abs(Z)))
    #im = plt.imshow(Z_im, cmap=bt_cm, vmin=Z_im.min(), vmax=Z_im.max(), extent=[0, w_m, 0, h_m])
    #im.set_interpolation('bicubic')#bilinear / nearest

    plt.imsave(filename, Z_im, cmap=bt_cm, vmin=Z_im.min(), vmax=Z_im.max())
    
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    
    #plt.suptitle('f: ' + "{0:.2f}".format(current_f) + ' Hz', fontsize=20)
    #cb = fig.colorbar(im)
    #plt.show()
    
    #plt.savefig(filename, bbox_inches='tight')  
    plt.clf()
    plt.close(fig)

#STEADY STATE SWEEP

"""
for i in range(0,350):
    current_f = 160**(1.01+i/400.0)
    omega = 2*np.pi*current_f
        
    eplo_p = np.dot(np.linalg.inv(-omega**2*M+K),F)

    #Add back zeros (boundaries)
    eplo = np.append(eplo_p[0:ix[0]],[0]*(len(ix)))
    eplo = np.append(eplo, eplo_p[ix[0]:])
    
    #Displacements only
    eplo = eplo[0::3]
    eplo = np.reshape(eplo,((h_i+1),(w_i+1)))
    
    X = np.linspace(0,w_m,w_i+1)
    Y = np.linspace(0,h_m,h_i+1)
    X,Y = np.meshgrid(X,Y)
    Z = np.real(eplo) 
    ssf.append(current_f)
    ssmag.append(np.sqrt(np.mean(np.square(Z))))
    #Z = np.multiply(1/np.max(np.abs(Z)),Z)
    
    fig, ax = plt.subplots() #RdBu, bone, etc (gg python colormaps)
    Z_im = np.sqrt(np.sqrt(np.abs(Z)))
    im = plt.imshow(Z_im, cmap=cm.binary, vmin=Z_im.min(), vmax=Z_im.max(), extent=[0, w_m, 0, h_m])
    im.set_interpolation('bicubic')#bilinear / nearest
    
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    
    plt.suptitle('f: ' + "{0:.2f}".format(current_f) + ' Hz', fontsize=20)
    #cb = fig.colorbar(im)
    #plt.show()
    
    if(i % 1 == 0):
        if int(i) < 10:
            plt.savefig('img000'+str(int(i))+'.png', bbox_inches='tight')  
        elif int(i) < 100:
            plt.savefig('img00'+str(int(i))+'.png', bbox_inches='tight')  
        elif int(i) < 1000:
            plt.savefig('img0'+str(int(i))+'.png', bbox_inches='tight')  
        else:
            plt.savefig('img'+str(int(i))+'.png', bbox_inches='tight')  
    plt.clf()
    plt.close(fig)

plt.plot(ssf,ssmag)
plt.xscale('log')
plt.yscale('log')
plt.show()
"""

#STEADY STATE ONE FREQUENCY
"""
f = 80
current_f = 160**(1.01+f/400.0)
omega = 2*np.pi*current_f
eplo_p = np.dot(np.linalg.inv(-omega**2*M+K),F)

#Add back zeros (boundaries)
eplo = np.append(eplo_p[0:ix[0]],[0]*(len(ix)))
eplo = np.append(eplo, eplo_p[ix[0]:])

#Displacements only
eplo = eplo[0::3]
eplo = np.reshape(eplo,((h_i+1),(w_i+1)))

X = np.linspace(0,w_m,w_i+1)
Y = np.linspace(0,h_m,h_i+1)
X,Y = np.meshgrid(X,Y)
Z = np.real(eplo) 

#Normalize
Z = np.multiply(1/np.max(np.abs(Z)),Z)

ci = np.arange(0,2*np.pi,0.01)
cx = np.cos(ci) * w_m*0.39 + w_m/2.0
cy = np.sin(ci) * h_m*0.39 + h_m/2.0
cz = [0] * len(ci)

frames = 50
for i in range(0,frames):
    amp = np.sin(i / (frames + 0.0) * 2 * np.pi)
    print amp
    
    Z_im = np.multiply(amp,Z)
        
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_wireframe(X,Y,Z_im)
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.set_zlim([-1,1])
    
    #ax3d = Axes3D(fig)
    ax.plot(xs=cx,ys=cy,zs=0, zdir='z', label='zs=0, zdir=z', color='r', linewidth=2.0)
    
    plt.show()
    
    
    if(i % 1 == 0):
        if int(i) < 10:
            plt.savefig('img000'+str(int(i))+'.png', bbox_inches='tight')  
        elif int(i) < 100:
            plt.savefig('img00'+str(int(i))+'.png', bbox_inches='tight')  
        elif int(i) < 1000:
            plt.savefig('img0'+str(int(i))+'.png', bbox_inches='tight')  
        else:
            plt.savefig('img'+str(int(i))+'.png', bbox_inches='tight')  
    
    plt.clf()
"""

for i in range(100, 20000, 100):
    generatePattern(i, 'chlandi/%d.png' % i)