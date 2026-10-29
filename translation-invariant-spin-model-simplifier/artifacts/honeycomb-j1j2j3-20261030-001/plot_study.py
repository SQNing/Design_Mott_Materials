import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'summary.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,
                     'axes.spines.top':False,'axes.spines.right':False})
colors=['#247ba0','#e07a35','#7b5ba7','#2a9d8f']
A=np.array([[np.sqrt(3)/2,1.5],[-np.sqrt(3)/2,1.5]])
basis=np.array([[0,0],[0,1.]])
keys=['P1-fourier-seeded-L2','P2-fourier-seeded-L2','P3-fourier-seeded-L2','P4-fourier-seeded-L36']
names=['Neel','Zigzag member','Stripy member','Spiral member']
fig,axs=plt.subplots(1,4,figsize=(14.2,4.6),layout='constrained')
for i,(ax,key,name) in enumerate(zip(axs,keys,names)):
    obs=d['observations'][key]
    n=np.array(obs['plot_spins']).reshape(tuple(obs['plot_shape'])+(2,3))
    cov=np.array(obs['plot_spins']).T@np.array(obs['plot_spins'])
    _,frame=np.linalg.eigh(cov);frame=frame[:,::-1]
    pos=[];vectors=[];sites={}
    for x in range(4):
        for y in range(4):
            for s in range(2):
                sites[x,y,s]=len(pos)
                pos.append(np.array([x,y])@A+basis[s])
                vectors.append(n[x%n.shape[0],y%n.shape[1],0,s]@frame)
    pos=np.array(pos);v=np.array(vectors)
    edges=[]
    for x in range(4):
        for y in range(4):
            for dx,dy in [(0,0),(-1,0),(0,-1)]:
                if (x+dx,y+dy,1) in sites:
                    edges.append([pos[sites[x,y,0]],pos[sites[x+dx,y+dy,1]]])
    ax.add_collection(LineCollection(edges,colors='#ccd2d6',linewidths=1,zorder=1))
    ax.scatter(pos[:,0],pos[:,1],s=18,color='#edf0f2',edgecolors='#9ea8ae',linewidths=.5,zorder=2)
    ax.quiver(pos[:,0],pos[:,1],v[:,0],v[:,1],angles='xy',scale_units='xy',scale=1.55,
              pivot='mid',color=colors[i],width=.013,headwidth=3.6,zorder=3)
    ax.set_aspect('equal');ax.axis('off')
    coupling=d['manifest']['coupling_points_selected_by_agent']['P'+str(i+1)]
    ax.set_title(f'{name}\n$(J_1,J_2,J_3)=({coupling[0]:g},{coupling[1]:g},{coupling[2]:g})$',pad=10)
    ax.text(.5,-.025,f"$E/(NS^2J_1)={obs['energy_per_site_unit_spin']:.6f}$",transform=ax.transAxes,ha='center')
fig.suptitle('Honeycomb Heisenberg model: finite-cell ground-state representatives',fontsize=15)
fig.supxlabel('P1-P3: 2 x 2 cells (repeated); P4: 36 x 36 (cropped). Zigzag and stripy belong to degenerate manifolds.\nSpin directions are shown in a freely rotated common spin frame within each panel.',fontsize=9)
fig.savefig(ROOT/'representative-states.png',dpi=180)
fig.savefig(ROOT/'representative-states.svg')
plt.close(fig)

fig,axs=plt.subplots(1,3,figsize=(14.2,4.5),layout='constrained')
ax=axs[0]
for group,col in [('J2',colors[0]),('J3',colors[1])]:
    vals=[]
    for suffix in ['off','half','control']:
        key='P2-intervention-'+(group+'-'+suffix if suffix!='control' else 'control')
        vals.append(d['observations'][key]['energy_per_site_unit_spin'])
    ax.plot([0,.5,1],vals,'o--',color=col,label=group+' scaled (8 x 8)')
ax.scatter([0,.5], [d['observations']['P2-J3-off-L36']['energy_per_site_unit_spin'],
                    d['observations']['P2-J3-half-L36']['energy_per_site_unit_spin']],
           marker='x',s=65,color='#b84a20',zorder=5,label='J3 controls (36 x 36)')
ax.set(xlabel='Coupling multiplier; other couplings fixed',ylabel='$E/(NS^2J_1)$',title='Independent coupling interventions')
ax.legend(fontsize=8,loc='lower right');ax.grid(alpha=.2)

ax=axs[1]
for j,group in enumerate(['P2','P3']):
    for k,seed in enumerate([31,97]):
        o=d['observations'][f'{group}-ground-L4-seed{seed}']
        weights=[]
        for q in [[.5,0,0],[0,.5,0],[.5,.5,0]]:
            weights.append(sum(p['weight'] for p in o['bravais_fourier_peaks'] if np.allclose(p['q'],q)))
        x=2*j+k
        bottom=0
        for l,w in enumerate(weights):
            ax.bar(x,w,bottom=bottom,color=[colors[0],colors[1],colors[2]][l],label=['M1','M2','M3'][l] if x==0 else None)
            bottom+=w
ax.set_xticks(range(4),['P2 / seed 31','P2 / seed 97','P3 / seed 31','P3 / seed 97'],rotation=15)
ax.set(ylabel='Sublattice-resolved Bravais Fourier weight',title='Different mixtures, equal energies',ylim=(0,1.15))
ax.legend(ncol=3,fontsize=8,loc='upper right')

ax=axs[2]
sizes=[4,6,8,12,36]
energies=[]
for L,seed in [(4,31),(6,53),(8,71),(12,83),(36,None)]:
    key=f'P4-ground-L{L}-seed{seed}' if seed else 'P4-fourier-seeded-L36'
    if L==12: key='P4-fourier-seeded-L12'
    energies.append(d['observations'][key]['energy_per_site_unit_spin'])
ax.plot(sizes,energies,'o--',color=colors[3],label='Finite-cell optimized energy')
ax.axhline(d['fourier']['P4']['energy_per_site_unit_spin'],color='#455a64',ls=':',label='Numerical continuum minimum')
ax.set(xlabel='L for L x L primitive cells',ylabel='$E/(NS^2J_1)$',title='Spiral commensurability error')
ax.set_xticks(sizes);ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.savefig(ROOT/'competition-diagnostics.png',dpi=180)
fig.savefig(ROOT/'competition-diagnostics.svg')
plt.close(fig)
print('PLOTS_READY')
