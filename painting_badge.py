from PIL import Image, ImageDraw, ImageFont
import sys
def badge(src, lockup='assets/img/logo-lockup.png', edge=3000):
    L=Image.open(lockup).convert('RGBA')
    paint=L.crop((0,0,L.size[0],498)); text=L.crop((0,498,L.size[0],L.size[1])); text=text.crop(text.getbbox())
    s=edge/max(src.size); src=src.resize((round(src.size[0]*s),round(src.size[1]*s)),Image.LANCZOS)
    W,H=src.size
    ph=int(max(W,H)*0.041); pw=round(paint.size[0]*ph/paint.size[1]); pl=paint.resize((pw,ph),Image.LANCZOS)
    th=int(ph*0.60); tw=round(text.size[0]*th/text.size[1]); tl=text.resize((tw,th),Image.LANCZOS)
    f=ImageFont.truetype('C:/Windows/Fonts/georgia.ttf',int(ph*0.205))
    t='arasteh.art'; bx=ImageDraw.Draw(src).textbbox((0,0),t,font=f); urlw=bx[2]-bx[0]
    pad=int(ph*0.16); gap=int(ph*0.14); colw=max(tw,urlw)
    boxw=pad+pw+gap+colw+pad; boxh=pad+ph+pad
    m=int(max(W,H)*0.012); x0=W-boxw-m; y0=H-boxh-m
    panel=Image.new('RGBA',(boxw,boxh),(0,0,0,0)); pd=ImageDraw.Draw(panel)
    pd.rounded_rectangle((0,0,boxw-1,boxh-1),radius=max(4,int(ph*0.12)),fill=(255,255,255,215))
    panel.paste(pl,(pad,pad),pl)
    cx=pad+pw+gap; ty=pad+int(ph*0.05)
    panel.paste(tl,(cx+(colw-tw)//2,ty),tl)
    uy=ty+th+int(ph*0.08)
    pd.text((cx+(colw-urlw)//2-bx[0],uy-bx[1]),t,fill=(40,40,40,255),font=f)
    out=src.convert('RGBA'); out.alpha_composite(panel,(x0,y0))
    return out.convert('RGB'),(x0,y0,boxw,boxh)
if __name__=='__main__':
    OUTD=sys.argv[2]
    out,(x0,y0,bw,bh)=badge(Image.open(sys.argv[1]).convert('RGB'))
    out.save(OUTD+'sample_01_overlay_small.jpg',quality=90)
    out.crop((x0-60,y0-60,out.size[0],out.size[1])).save(OUTD+'sample_01_overlay_small_zoom.png')
