"""Choose trustworthy caret coordinates, not stale 0,0 window carets."""
def choose_anchor(native,uia,window):
    left,top,right,bottom=window
    def inside(p):return p and left<=p['x']<=right and top<=p['y']<=bottom
    valid_native=inside(native) and 4<=native.get('height',0)<=100 and native.get('width',0)<=80
    if uia and inside(uia):
        source=uia.get('source','')
        if source in ('uia-caret-active','xterm-input-cell','uia-caret','uia-selection'):
            return {'x':uia['x'],'y':uia['y'],'source':source,'caret':True}
        focus=uia.get('focus',{}).get('bounds')
        if valid_native and focus:
            x,y,w,h=focus
            if not(x-4<=native['x']<=x+w+4 and y-4<=native['y']<=y+h+4):valid_native=False
        if valid_native:return {'x':native['x'],'y':native['y'],'source':'native-caret','caret':True}
        # Do not label the root document / full application rectangle an editor.
        if uia.get('width',0)<(right-left)*.9 or uia.get('height',0)<(bottom-top)*.7:
            return {'x':uia['x'],'y':uia['y'],'source':source or 'uia-editor','caret':True}
    if valid_native:return {'x':native['x'],'y':native['y'],'source':'native-caret','caret':True}
    return {'x':(left+right)//2-240,'y':bottom-120,'source':'window-fallback','caret':False}
